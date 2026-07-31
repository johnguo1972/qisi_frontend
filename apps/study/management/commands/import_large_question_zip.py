"""Server-side, resumable importer for large JSON-array question ZIPs."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.common.codegen import generate_question_system_id
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption


QID_PREFIX = "large_import_qid:"
SUBJECTS = {"physics": "physics", "物理": "physics", "math": "math", "数学": "math"}
TYPE_MAP = {"single_choice": "single_choice", "multiple_choice": "multiple_choice", "fill_blank": "fill_blank", "short_answer": "short_answer", "solution": "short_answer", "calculation": "computation", "computation": "computation", "true_false": "true_false", "proof": "proof", "experiment": "short_answer"}


class Command(BaseCommand):
    help = "Import large question ZIPs in chunks without the HTTP 50MB limit."

    def add_arguments(self, parser):
        parser.add_argument("zip_path")
        parser.add_argument("--subject", default="physics")
        parser.add_argument("--chunk-size", type=int, default=50)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        zip_path = Path(opts["zip_path"])
        if not zip_path.exists():
            raise CommandError(f"ZIP not found: {zip_path}")
        subject = SUBJECTS.get(opts["subject"], opts["subject"])
        chunk_size = max(1, opts["chunk_size"])
        with zipfile.ZipFile(zip_path) as zf:
            json_names = [i.filename for i in zf.infolist() if i.filename.lower().endswith(".json")]
            if not json_names:
                raise CommandError("No JSON files found")
            total = 0
            stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
            paper = None
            if not opts["dry_run"]:
                paper, _ = ExamPaper.objects.get_or_create(
                    source_file_path=str(zip_path),
                    defaults={"title": zip_path.stem, "subject": subject, "stage": "junior", "grade": "初中", "paper_type": "large_json_import", "status": "reviewing", "uploaded_by": None},
                )
            for name in sorted(json_names):
                try:
                    data = json.loads(zf.read(name))
                except Exception as exc:
                    self.stderr.write(f"FAILED JSON {name}: {exc}")
                    continue
                if not isinstance(data, list):
                    continue
                for offset in range(0, len(data), chunk_size):
                    chunk = data[offset:offset + chunk_size]
                    for qdata in chunk:
                        total += 1
                        if opts["dry_run"]:
                            continue
                        try:
                            action = self.import_one(zf, qdata, paper, subject)
                            stats[action] += 1
                        except Exception as exc:
                            stats["failed"] += 1
                            self.stderr.write(f"FAILED {qdata.get('qid') or qdata.get('number')}: {exc}")
                    self.stdout.write(f"processed={total} created={stats['created']} updated={stats['updated']} failed={stats['failed']}")
            if paper:
                paper.total_questions = ExamQuestion.objects.filter(paper=paper).count()
                paper.save(update_fields=["total_questions", "updated_at"])
            self.stdout.write(self.style.SUCCESS(json.dumps({"total": total, **stats}, ensure_ascii=False)))

    def import_one(self, zf, data, paper, subject):
        qid = str(data.get("qid") or "").strip()
        stem = str(data.get("stem") or "").strip()
        if not stem:
            return "skipped"
        marker = f"{QID_PREFIX}{qid}" if qid else ""
        existing = ExamQuestion.objects.filter(raw_text=marker).first() if marker else None
        if existing is None:
            digest = hashlib.sha256(stem.encode("utf-8")).hexdigest()
            existing = ExamQuestion.objects.filter(subject=subject, stem=stem).first()
            if existing is None:
                existing = ExamQuestion.objects.filter(subject=subject, raw_text__contains=digest).first()
        answer = data.get("answer", "")
        if isinstance(answer, dict):
            answer = answer.get("raw", "") or answer.get("text", "")
        values = {
            "paper": paper, "question_no": str(data.get("number") or data.get("source_number") or ""),
            "paper_question_no": str(data.get("source_number") or data.get("number") or ""),
            "question_type": TYPE_MAP.get(data.get("question_type"), "unknown"), "subject": subject,
            "stem": stem, "answer": str(answer or ""), "analysis": str(data.get("analysis") or ""),
            "solution": str(data.get("solution") or ""), "knowledge_points": data.get("knowledge_points") or [],
            "difficulty": data.get("difficulty") or 3, "page_start": data.get("page") or 0, "page_end": data.get("page") or 0,
            "raw_text": f"{marker}\nsha256:{hashlib.sha256(stem.encode('utf-8')).hexdigest()}",
            "parse_status": "large_json_import", "review_status": "need_review", "need_review": True,
            "source_collection": paper.title, "collected_at": timezone.now(),
        }
        with transaction.atomic():
            if existing:
                for key, value in values.items():
                    if key != "paper":
                        setattr(existing, key, value)
                existing.save()
                question = existing
                action = "updated"
            else:
                values["system_id"] = generate_question_system_id("P")
                question = ExamQuestion.objects.create(**values)
                action = "created"
            options = data.get("options") or []
            if isinstance(options, dict):
                options = [{"label": k, "content": v} for k, v in options.items()]
            QuestionOption.objects.filter(question=question).delete()
            for index, option in enumerate(options):
                if isinstance(option, dict):
                    QuestionOption.objects.create(question=question, option_label=str(option.get("label") or chr(65 + index)), content=str(option.get("content") or option.get("text") or ""), sort_order=index)
            if action == "created":
                self.save_images(zf, data, paper, question)
        return action

    def save_images(self, zf, data, paper, question):
        for index, image in enumerate(data.get("images") or []):
            if not isinstance(image, dict):
                continue
            local = image.get("local") or image.get("file") or ""
            filename = os.path.basename(local)
            if not filename:
                continue
            matches = [n for n in zf.namelist() if n.endswith("/images/" + filename) or n.endswith("/" + filename)]
            if not matches:
                continue
            rel_dir = Path("exams") / "large_imports" / str(paper.id)
            dest_dir = Path(settings.MEDIA_ROOT) / rel_dir
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_name = f"{question.id}_{filename}"
            with zf.open(matches[0]) as src, open(dest_dir / dest_name, "wb") as dst:
                shutil.copyfileobj(src, dst)
            QuestionImage.objects.update_or_create(question=question, sort_order=index, defaults={"paper": paper, "image_type": "diagram", "file_path": str(rel_dir / dest_name).replace("\\", "/")})
