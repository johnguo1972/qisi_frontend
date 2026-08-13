"""Cross-check the imported JSON package against database and course records."""
from __future__ import annotations

import hashlib
import json
import posixpath
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.courses.models import Course, CourseQuestionLink
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption
from apps.study.models import QuestionTag, QuestionTagRelation


EXPECTED_SHA256 = "5eea2fada6b1db82ecd3f0802352df0cdf02636165a4bbdc2bcd15d95be942d7"
EXPECTED_COUNT = 277
TAG_NAME = "9\u5e74\u7ea7\u79cb\u5b63\u73ed\u8bfe\u4ef6\u7ec3\u4e60"
COURSE_NAME = "\u4e5d\u5e74\u7ea7\u7269\u7406\u79cb\u5b63\u73ed\u8bfe\u4ef6\u7ec3\u4e60"


class Command(BaseCommand):
    help = "Verify Grade 9 autumn JSON import, course links and searchable tag."

    def add_arguments(self, parser):
        parser.add_argument("zip_path")
        parser.add_argument("--paper-id", required=True)
        parser.add_argument("--course-id", default=None)
        parser.add_argument("--tag-name", default=TAG_NAME)
        parser.add_argument("--allow-sha-mismatch", action="store_true")

    def handle(self, *args, **opts):
        zip_path = Path(opts["zip_path"]).expanduser().resolve()
        if not zip_path.is_file():
            raise CommandError(f"ZIP not found: {zip_path}")
        sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if sha != EXPECTED_SHA256 and not opts["allow_sha_mismatch"]:
            raise CommandError(f"ZIP SHA256 mismatch: {sha}")
        try:
            paper = ExamPaper.objects.get(id=opts["paper_id"])
        except ExamPaper.DoesNotExist as exc:
            raise CommandError("paper not found") from exc

        with zipfile.ZipFile(zip_path) as zf:
            root = next(n.split("/", 1)[0] for n in zf.namelist() if "/" in n)
            package = json.loads(zf.read(f"{root}/all_questions.json"))
            expected = package["questions"]
            asset_paths = {}
            for name in zf.namelist():
                if name.startswith(f"{root}/assets/") and not name.endswith("/"):
                    basename = posixpath.basename(name)
                    if basename in asset_paths:
                        raise CommandError(f"duplicate asset basename in ZIP: {basename}")
                    asset_paths[basename] = name
            if paper.source_package_id != package.get("paper", {}).get("paper_id"):
                errors = ["paper source_package_id does not match ZIP"]
            else:
                errors = []
            actual = list(ExamQuestion.objects.filter(paper=paper))
            if len(expected) != EXPECTED_COUNT:
                errors.append(f"source questions={len(expected)}")
            if len(actual) != len(expected):
                errors.append(f"database questions={len(actual)} expected={len(expected)}")
            by_external = {q.source_external_id: q for q in actual}
            if len(by_external) != len(actual):
                errors.append("database source_external_id is not unique")
            expected_options = expected_images = expected_subquestions = expected_tables = 0
            missing_media = 0
            for qdata in expected:
                external_id = qdata.get("question_id")
                q = by_external.get(external_id)
                if q is None:
                    errors.append(f"missing question {external_id}")
                    continue
                if q.stem != (qdata.get("stem") or ""):
                    errors.append(f"stem mismatch {external_id}")
                if q.source_question_type != qdata.get("question_type"):
                    errors.append(f"source type mismatch {external_id}")
                expected_options += len(qdata.get("options") or [])
                expected_subquestions += len(qdata.get("subquestions") or [])
                expected_tables += len(qdata.get("tables") or [])
                options = list(q.options.order_by("sort_order", "id"))
                source_options = qdata.get("options") or []
                if [(o.option_label, o.content) for o in options] != [
                    (str(o.get("label") or chr(65 + i)), str(o.get("content") or ""))
                    for i, o in enumerate(source_options)
                ]:
                    errors.append(f"options mismatch {external_id}")
                if (q.subquestions or []) != (qdata.get("subquestions") or []):
                    errors.append(f"subquestions mismatch {external_id}")
                if (q.tables or []) != (qdata.get("tables") or []):
                    errors.append(f"tables mismatch {external_id}")
                image_refs = []
                for key in ("illustrations", "formula_assets"):
                    image_refs.extend(
                        ("diagram" if key == "illustrations" else "formula", item)
                        for item in (qdata.get(key) or [])
                    )
                expected_images += len(image_refs)
                db_images = list(q.images.order_by("image_type", "sort_order", "id"))
                if len(db_images) != len(image_refs):
                    errors.append(f"image count mismatch {external_id}")
                unmatched_images = list(db_images)
                for image_type, item in image_refs:
                    filename = posixpath.basename(str(item.get("file") or ""))
                    match = next(
                        (
                            image for image in unmatched_images
                            if image.image_type == image_type
                            and image.file_path.endswith("_" + filename)
                        ),
                        None,
                    )
                    if match is None:
                        errors.append(f"image reference mismatch {external_id}: {filename}")
                    else:
                        unmatched_images.remove(match)
                if unmatched_images:
                    errors.append(f"image reference mismatch {external_id}")
                for image in db_images:
                    media_path = Path(settings.MEDIA_ROOT) / image.file_path
                    if not media_path.is_file():
                        missing_media += 1
                        continue
                    filename = posixpath.basename(image.file_path).split("_", 1)[-1]
                    zip_name = asset_paths.get(filename)
                    if not zip_name:
                        errors.append(f"media asset not found in ZIP {external_id}: {filename}")
                        continue
                    disk_sha = hashlib.sha256(media_path.read_bytes()).hexdigest()
                    zip_sha = hashlib.sha256(zf.read(zip_name)).hexdigest()
                    if disk_sha != zip_sha:
                        errors.append(f"media content mismatch {external_id}: {filename}")
            actual_options = QuestionOption.objects.filter(question__in=actual).count()
            actual_images = QuestionImage.objects.filter(question__in=actual).count()
            if actual_options != expected_options:
                errors.append(f"options total={actual_options} expected={expected_options}")
            if actual_images != expected_images:
                errors.append(f"images total={actual_images} expected={expected_images}")
            nonempty_answers = ExamQuestion.objects.filter(pk__in=[q.id for q in actual]).exclude(answer="").exclude(answer__isnull=True).count()
            nonempty_analysis = ExamQuestion.objects.filter(pk__in=[q.id for q in actual]).exclude(analysis="").exclude(analysis__isnull=True).count()
            if nonempty_answers or nonempty_analysis:
                errors.append(f"unexpected answers={nonempty_answers} analysis={nonempty_analysis}")
            if missing_media:
                errors.append(f"missing media files={missing_media}")
            missing_tag_json = sum(
                1 for question in actual
                if opts["tag_name"] not in (question.tags or [])
            )
            if missing_tag_json:
                errors.append(f"questions missing tag JSON={missing_tag_json}")

            course_result = None
            if opts.get("course_id"):
                try:
                    course = Course.objects.get(id=opts["course_id"], is_deleted=False)
                except Course.DoesNotExist as exc:
                    raise CommandError("course not found") from exc
            else:
                course = Course.objects.filter(name=COURSE_NAME, is_deleted=False).first()
            if course:
                links = CourseQuestionLink.objects.filter(course=course, is_deleted=False)
                if links.count() != EXPECTED_COUNT:
                    errors.append(f"course links={links.count()} expected={EXPECTED_COUNT}")
                linked_ids = set(links.values_list("question_id", flat=True))
                actual_ids = {question.id for question in actual}
                if linked_ids != actual_ids:
                    errors.append("course links do not match imported question set")
                if CourseQuestionLink.objects.filter(
                    course=course, is_deleted=False, tree_node__isnull=True
                ).exists():
                    errors.append("course contains question without lesson node")
                if course.tree_nodes.count() != 8:
                    errors.append(f"course nodes={course.tree_nodes.count()} expected=8")
                course_result = {"course_id": str(course.id), "links": links.count()}
            else:
                errors.append("course not found")

            try:
                tag = QuestionTag.objects.get(name=opts["tag_name"])
                tag_relations = QuestionTagRelation.objects.filter(tag=tag, question__in=actual).count()
                if tag_relations != EXPECTED_COUNT or tag.question_count != EXPECTED_COUNT:
                    errors.append(f"tag relations={tag_relations} count={tag.question_count}")
                all_tag_question_ids = set(
                    QuestionTagRelation.objects.filter(tag=tag).values_list("question_id", flat=True)
                )
                if all_tag_question_ids != {question.id for question in actual}:
                    errors.append("tag relations do not match imported question set")
                searchable_count = ExamQuestion.objects.filter(
                    id__in=[question.id for question in actual], tags__contains=[opts["tag_name"]]
                ).count()
                if searchable_count != EXPECTED_COUNT:
                    errors.append(f"searchable tag questions={searchable_count}")
                tag_result = {"tag_id": str(tag.id), "relations": tag_relations, "question_count": tag.question_count}
            except QuestionTag.DoesNotExist:
                errors.append("tag not found")
                tag_result = None

        result = {
            "status": "passed" if not errors else "failed",
            "sha256": sha,
            "paper_id": str(paper.id),
            "questions": len(actual),
            "options": actual_options,
            "images": actual_images,
            "subquestions": expected_subquestions,
            "tables": expected_tables,
            "missing_media": missing_media,
            "course": course_result,
            "tag": tag_result,
            "errors": errors[:100],
        }
        self.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True))
        if errors:
            raise CommandError("verification failed")
