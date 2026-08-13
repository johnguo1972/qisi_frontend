"""Import the 260813 Grade 9 autumn JSON practice package.

This command is intentionally separate from the legacy SQL importer and from
the generic large-array ZIP importer.  It is idempotent by the package's
external paper/question identifiers and preserves the source JSON fields that
the generic importer did not model.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.common.codegen import generate_paper_code
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption


EXPECTED_PACKAGE_ID = "TF_2023_T3_G9_PHYSICS_0CF24731"
EXPECTED_SHA256 = "5eea2fada6b1db82ecd3f0802352df0cdf02636165a4bbdc2bcd15d95be942d7"
EXPECTED_COUNT = 277
SUBJECT = "physics"
SUBJECT_LABEL = "\u7269\u7406"
GRADE_LABEL = "\u4e5d\u5e74\u7ea7"
COURSE_TITLE = "\u4e5d\u5e74\u7ea7\u7269\u7406\u79cb\u5b63\u73ed\u8bfe\u4ef6\u7ec3\u4e60"

TYPE_MAP = {
    "single_choice": "single_choice",
    "multiple_choice": "multiple_choice",
    "fill_blank": "fill_blank",
    "short_answer": "short_answer",
    "calculation": "computation",
    "computation": "computation",
    "true_false": "true_false",
    "judgement": "true_false",
    "proof": "proof",
    "experiment": "short_answer",
    "compound": "short_answer",
    "solution": "short_answer",
}


def _safe_zip_name(name: str) -> bool:
    """Reject absolute and traversal names before reading/extracting a ZIP."""
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return not path.is_absolute() and ".." not in path.parts


def _json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class Command(BaseCommand):
    help = "Import the Grade 9 autumn JSON practice package (separate from legacy SQL import)."

    # This importer deliberately does not call the legacy question-ID helper.
    # The legacy helper keeps a counter by the exact subject string, while the
    # existing data uses the P prefix and the local counter can be out of sync.
    # Allocating from the current database maximum makes this import safe for
    # the existing appdb and keeps it independent from the old SQL importer.
    system_id_prefix = "P"

    def add_arguments(self, parser):
        parser.add_argument("zip_path")
        parser.add_argument("--subject", default=SUBJECT)
        parser.add_argument("--teacher-id", default=None)
        parser.add_argument("--chunk-size", type=int, default=50)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--allow-sha-mismatch", action="store_true")

    def handle(self, *args, **opts):
        zip_path = Path(opts["zip_path"]).expanduser().resolve()
        if not zip_path.is_file():
            raise CommandError(f"ZIP not found: {zip_path}")
        subject = opts["subject"]
        if subject not in (SUBJECT, SUBJECT_LABEL):
            raise CommandError(f"This importer only supports physics/物理, got: {subject}")

        actual_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if actual_sha != EXPECTED_SHA256 and not opts["allow_sha_mismatch"]:
            raise CommandError(
                f"ZIP SHA256 mismatch: expected {EXPECTED_SHA256}, got {actual_sha}; "
                "use --allow-sha-mismatch only after manual review"
            )

        with zipfile.ZipFile(zip_path) as zf:
            package, manifest, root, assets = self.read_package(zf)
            questions = package.get("questions")
            if not isinstance(questions, list) or len(questions) != EXPECTED_COUNT:
                raise CommandError(f"expected {EXPECTED_COUNT} questions, got {len(questions or [])}")
            self.validate_package(zf, root, manifest, questions, assets)
            stats = self.preview_stats(questions, assets)
            if opts["dry_run"]:
                stats.update({"sha256": actual_sha, "package_id": manifest["paper"]["paper_id"]})
                self.stdout.write(json.dumps(stats, ensure_ascii=False, sort_keys=True))
                return

            teacher = self.get_teacher(opts.get("teacher_id"))
            paper, paper_created = self.get_or_create_paper(
                zip_path, actual_sha, manifest, teacher
            )
            self.next_system_id_sequence = self.get_next_system_id_sequence()
            totals = {"created": 0, "updated": 0, "failed": 0, "options": 0, "images": 0}
            chunk_size = max(1, opts["chunk_size"])
            for start in range(0, len(questions), chunk_size):
                for qdata in questions[start:start + chunk_size]:
                    try:
                        with transaction.atomic():
                            action, option_count, image_count = self.import_question(
                                zf, paper, qdata, assets
                            )
                        totals[action] += 1
                        totals["options"] += option_count
                        totals["images"] += image_count
                    except Exception as exc:  # one bad record must be visible
                        totals["failed"] += 1
                        self.stderr.write(
                            f"FAILED {qdata.get('question_id', '<unknown>')}: {exc}"
                        )
                self.stdout.write(
                    f"processed={min(start + chunk_size, len(questions))} "
                    f"created={totals['created']} updated={totals['updated']} "
                    f"failed={totals['failed']}"
                )

            if totals["failed"]:
                raise CommandError(json.dumps({"status": "failed", **totals}, ensure_ascii=False))
            paper.total_questions = ExamQuestion.objects.filter(paper=paper).count()
            paper.has_solution = False
            paper.status = "reviewing"
            paper.save(update_fields=["total_questions", "has_solution", "status", "updated_at"])
            self.stdout.write(self.style.SUCCESS(json.dumps({
                "status": "success", "paper_id": str(paper.id),
                "paper_created": paper_created, **totals,
            }, ensure_ascii=False)))

    def read_package(self, zf):
        names = zf.namelist()
        unsafe = [name for name in names if not _safe_zip_name(name)]
        if unsafe:
            raise CommandError(f"unsafe ZIP path: {unsafe[0]}")
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            raise CommandError(f"expected one package root, got {sorted(roots)}")
        root = next(iter(roots))
        manifest_name = f"{root}/manifest.json"
        package_name = f"{root}/all_questions.json"
        if manifest_name not in names or package_name not in names:
            raise CommandError("ZIP must contain manifest.json and all_questions.json")
        manifest = json.loads(zf.read(manifest_name))
        package = json.loads(zf.read(package_name))
        asset_names = [
            name for name in names
            if name.startswith(f"{root}/assets/") and not name.endswith("/")
        ]
        assets = {}
        for name in asset_names:
            base = posixpath.basename(name)
            if base in assets:
                raise CommandError(f"duplicate asset basename: {base}")
            assets[base] = name
        return package, manifest, root, assets

    def validate_package(self, zf, root, manifest, questions, assets):
        paper = manifest.get("paper") or {}
        if paper.get("paper_id") != EXPECTED_PACKAGE_ID:
            raise CommandError(f"unexpected package id: {paper.get('paper_id')}")
        qids = [q.get("question_id") for q in questions]
        if any(not qid for qid in qids) or len(set(qids)) != len(qids):
            raise CommandError("question_id must be present and unique")
        json_names = {
            f"{root}/questions/question_{index:03d}.json"
            for index in range(1, EXPECTED_COUNT + 1)
        }
        missing = sorted(json_names.difference(zf.namelist()))
        if missing:
            raise CommandError(f"missing question JSON: {missing[0]}")
        references = set()
        for qdata in questions:
            qtype = qdata.get("question_type")
            if qtype not in TYPE_MAP:
                raise CommandError(f"unsupported question_type {qtype!r} for {qdata.get('question_id')}")
            question_number = str(qdata.get("question_id", "")).rsplit("_Q", 1)[-1]
            question_file = f"{root}/questions/question_{int(question_number):03d}.json"
            single_question = json.loads(zf.read(question_file))
            if _json_text(single_question) != _json_text(qdata):
                raise CommandError(f"combined/single JSON mismatch: {qdata.get('question_id')}")
            for key in ("illustrations", "formula_assets"):
                for asset in qdata.get(key) or []:
                    filename = posixpath.basename(str(asset.get("file") or ""))
                    if not filename or filename not in assets:
                        raise CommandError(
                            f"missing {key} asset {asset.get('file')} for {qdata.get('question_id')}"
                        )
                    references.add(filename)
        if references != set(assets):
            missing = sorted(set(assets).difference(references))
            extra = sorted(references.difference(assets))
            raise CommandError(f"asset reference mismatch: missing={missing[:1]} extra={extra[:1]}")

    def preview_stats(self, questions, assets):
        return {
            "questions": len(questions),
            "options": sum(len(q.get("options") or []) for q in questions),
            "subquestions": sum(len(q.get("subquestions") or []) for q in questions),
            "tables": sum(len(q.get("tables") or []) for q in questions),
            "images": sum(
                len(q.get("illustrations") or []) + len(q.get("formula_assets") or [])
                for q in questions
            ),
            "assets": len(assets),
            "answers": sum(bool((q.get("answer") or {}).get("raw")) for q in questions),
            "analysis": sum(bool(q.get("analysis")) for q in questions),
        }

    def get_teacher(self, teacher_id):
        if not teacher_id:
            return None
        from apps.accounts.models import UserAccount
        try:
            return UserAccount.objects.get(id=teacher_id, role_type="teacher")
        except UserAccount.DoesNotExist as exc:
            raise CommandError(f"teacher not found or not teacher: {teacher_id}") from exc

    def get_or_create_paper(self, zip_path, sha256, manifest, teacher):
        paper_info = manifest["paper"]
        package_id = paper_info["paper_id"]
        existing = ExamPaper.objects.filter(source_package_id=package_id).first()
        if existing is not None:
            changed = []
            for field, value in {
                "title": COURSE_TITLE,
                "subject": SUBJECT_LABEL,
                "stage": "junior",
                "grade": GRADE_LABEL,
                "paper_type": "json_import_practice",
                "has_solution": False,
                "total_questions": EXPECTED_COUNT,
                "source_sha256": sha256,
                "source_file_path": str(zip_path),
                "uploaded_by": teacher,
                "status": "reviewing",
            }.items():
                if value is not None and getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed.append(field)
            if changed:
                existing.save(update_fields=changed + ["updated_at"])
            return existing, False
        defaults = {
            "title": COURSE_TITLE,
            "paper_code": generate_paper_code(SUBJECT_LABEL, GRADE_LABEL),
            "region": paper_info.get("title", ""),
            "subject": SUBJECT_LABEL,
            "stage": "junior",
            "grade": GRADE_LABEL,
            "paper_type": "json_import_practice",
            "has_solution": False,
            "source_file_path": str(zip_path),
            "status": "reviewing",
            "total_questions": EXPECTED_COUNT,
            "uploaded_by": teacher,
            "source_sha256": sha256,
        }
        paper = ExamPaper.objects.create(source_package_id=package_id, **defaults)
        return paper, True

    def get_next_system_id_sequence(self):
        """Return the first unused numeric suffix for a P-prefixed system ID."""
        max_sequence = 0
        existing_ids = ExamQuestion.objects.filter(
            system_id__startswith=self.system_id_prefix
        ).values_list("system_id", flat=True)
        for system_id in existing_ids:
            if not system_id or not system_id.startswith(self.system_id_prefix):
                continue
            suffix = system_id[len(self.system_id_prefix):]
            # Existing IDs are P + five hexadecimal characters. Ignore any
            # unrelated legacy values that merely happen to start with P.
            if len(suffix) != 5:
                continue
            try:
                max_sequence = max(max_sequence, int(suffix, 16))
            except ValueError:
                continue
        return max_sequence + 1

    def allocate_system_id(self):
        """Allocate a unique P-prefixed ID without using the legacy counter."""
        sequence = getattr(self, "next_system_id_sequence", 1)
        while sequence <= 0xFFFFF:
            system_id = f"{self.system_id_prefix}{sequence:05X}"
            if not ExamQuestion.objects.filter(system_id=system_id).exists():
                self.next_system_id_sequence = sequence + 1
                return system_id
            sequence += 1
        raise CommandError("No unused P-prefixed system_id remains")

    def import_question(self, zf, paper, qdata, assets):
        external_id = qdata["question_id"]
        qtype_raw = qdata["question_type"]
        qtype = TYPE_MAP[qtype_raw]
        answer = qdata.get("answer") or {}
        answer_raw = answer.get("raw") if isinstance(answer, dict) else answer
        source = qdata.get("source") or {}
        quality = qdata.get("quality") or {}
        defaults = {
            "paper": paper,
            "question_no": str(qdata.get("question_no") or ""),
            "paper_question_no": f"{paper.paper_code}-{qdata.get('question_no') or external_id}",
            "source_external_id": external_id,
            "source_question_type": qtype_raw,
            "question_type": qtype,
            "subject": SUBJECT,
            "section_title": qdata.get("section") or "",
            "stem": qdata.get("stem") or "",
            "material": qdata.get("material"),
            "answer": str(answer_raw or ""),
            "analysis": str(qdata.get("analysis") or ""),
            "solution": "",
            "knowledge_points": [],
            "subquestions": qdata.get("subquestions") or [],
            "tables": qdata.get("tables") or [],
            "page_start": source.get("page_start"),
            "page_end": source.get("page_end"),
            "sort_order": int(external_id.rsplit("_Q", 1)[-1].lstrip("0") or "0"),
            "confidence": 1.0,
            "need_review": bool(quality.get("requires_review", True)),
            "review_status": "need_review",
            "parse_status": "g9_autumn_json_import",
            "source_collection": COURSE_TITLE,
            "creator_name": getattr(paper.uploaded_by, "display_name", "") if paper.uploaded_by else "",
            "collected_at": timezone.now(),
            "barcode_data": None,
            "raw_text": f"source_package_id:{paper.source_package_id}\n" + _json_text(qdata),
        }
        question = ExamQuestion.objects.filter(
            paper=paper, source_external_id=external_id
        ).first()
        if question is None:
            defaults["system_id"] = self.allocate_system_id()
            question = ExamQuestion.objects.create(**defaults)
            action = "created"
        else:
            for field, value in defaults.items():
                if field not in ("paper", "system_id"):
                    setattr(question, field, value)
            question.save()
            action = "updated"

        QuestionOption.objects.filter(question=question).delete()
        options = qdata.get("options") or []
        for index, option in enumerate(options):
            QuestionOption.objects.create(
                question=question,
                option_label=str(option.get("label") or chr(65 + index)),
                content=str(option.get("content") or ""),
                sort_order=index,
            )

        media_prefix = f"exams/json_imports/{paper.id}/"
        QuestionImage.objects.filter(
            question=question, file_path__startswith=media_prefix
        ).delete()
        image_count = 0
        for image_type, key in (("diagram", "illustrations"), ("formula", "formula_assets")):
            for index, asset in enumerate(qdata.get(key) or []):
                filename = posixpath.basename(str(asset.get("file") or ""))
                zip_name = assets[filename]
                rel_dir = Path("exams") / "json_imports" / str(paper.id)
                dest_dir = Path(settings.MEDIA_ROOT) / rel_dir
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_name = f"{question.id}_{filename}"
                dest_path = dest_dir / dest_name
                with zf.open(zip_name) as source_file, open(dest_path, "wb") as target:
                    shutil.copyfileobj(source_file, target)
                QuestionImage.objects.update_or_create(
                    question=question,
                    image_type=image_type,
                    sort_order=index,
                    defaults={
                        "paper": paper,
                        "file_path": f"{rel_dir.as_posix()}/{dest_name}",
                        "description": asset.get("alt_text") or asset.get("recognized_text") or "",
                    },
                )
                image_count += 1
        return action, len(options), image_count
