"""Import the already-verified local Grade 9 autumn records on the server."""
from __future__ import annotations

import json
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


EXPECTED_PACKAGE_ID = "TF_2023_T3_G9_PHYSICS_0CF24731"
EXPECTED_COUNTS = {
    "papers": 1,
    "questions": 277,
    "options": 528,
    "images": 337,
    "courses": 1,
    "trees": 8,
    "course_links": 277,
    "tags": 1,
    "tag_relations": 277,
    "variant_tasks": 2,
}


class Command(BaseCommand):
    help = "Import the exported Grade 9 autumn records without re-parsing the ZIP."

    def add_arguments(self, parser):
        parser.add_argument("payload")
        parser.add_argument("--teacher-mobile", required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        from apps.accounts.models import UserAccount
        from apps.papers.models import ExamPaper

        payload_path = Path(opts["payload"]).resolve()
        if not payload_path.is_file():
            raise CommandError(f"migration payload not found: {payload_path}")
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        meta = payload.get("meta") or {}
        if meta.get("package_id") != EXPECTED_PACKAGE_ID:
            raise CommandError("unexpected source package")
        for name, expected in EXPECTED_COUNTS.items():
            actual = len(payload.get(name) or [])
            if actual != expected:
                raise CommandError(f"{name}: expected {expected}, got {actual}")

        try:
            teacher = UserAccount.objects.get(
                mobile=opts["teacher_mobile"], role_type="teacher"
            )
        except UserAccount.DoesNotExist as exc:
            raise CommandError("server teacher not found by mobile") from exc

        if ExamPaper.objects.filter(source_package_id=EXPECTED_PACKAGE_ID).exists():
            raise CommandError("source package already exists on server; refusing duplicate import")

        if opts["dry_run"]:
            self.stdout.write(self.style.SUCCESS(json.dumps({
                "status": "dry-run",
                "teacher_id": str(teacher.id),
                "counts": {name: len(payload[name]) for name in EXPECTED_COUNTS},
            }, ensure_ascii=False)))
            return

        with transaction.atomic():
            for name in ("papers", "questions", "options", "images", "courses", "trees", "tags", "course_links", "tag_relations", "variant_tasks"):
                self.import_records(payload.get(name) or [], teacher)

            paper = ExamPaper.objects.get(source_package_id=EXPECTED_PACKAGE_ID)
            paper.source_file_path = "/mnt/datadisk0/qisi/import_staging/九年级物理讲义_JSON解析.zip"
            paper.uploaded_by_id = teacher.id
            paper.save(update_fields=["source_file_path", "uploaded_by", "updated_at"])

        self.stdout.write(self.style.SUCCESS(json.dumps({
            "status": "success",
            "teacher_id": str(teacher.id),
            "package_id": EXPECTED_PACKAGE_ID,
            "counts": {name: len(payload[name]) for name in EXPECTED_COUNTS},
        }, ensure_ascii=False)))

    def import_records(self, records, teacher):
        if not records:
            return
        model_label = records[0]["model"]
        model_name = model_label.split(".")[-1]
        model_map = {
            "papers.exampaper": "apps.papers.models.ExamPaper",
            "parser.examquestion": "apps.parser.models.ExamQuestion",
            "parser.questionoption": "apps.parser.models.QuestionOption",
            "parser.questionimage": "apps.parser.models.QuestionImage",
            "courses.course": "apps.courses.models.Course",
            "courses.coursetree": "apps.courses.models.CourseTree",
            "courses.coursequestionlink": "apps.courses.models.CourseQuestionLink",
            "courses.varianttask": "apps.courses.models.VariantTask",
            "study.questiontag": "apps.study.models.QuestionTag",
            "study.questiontagrelation": "apps.study.models.QuestionTagRelation",
        }
        dotted = model_map.get(model_label)
        if not dotted:
            raise CommandError(f"unsupported fixture model: {model_label}")
        module_name, class_name = dotted.rsplit(".", 1)
        module = __import__(module_name, fromlist=[class_name])
        model = getattr(module, class_name)
        for item in serializers.deserialize("json", json.dumps(records, ensure_ascii=False)):
            obj = item.object
            if model_label in ("papers.exampaper", "courses.course", "study.questiontag"):
                if hasattr(obj, "teacher_id"):
                    obj.teacher_id = teacher.id
                if hasattr(obj, "uploaded_by_id"):
                    obj.uploaded_by_id = teacher.id
                if hasattr(obj, "created_by_id"):
                    obj.created_by_id = teacher.id
            obj.save()
