"""Export the local Grade 9 autumn practice records for a server-side import."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import django
from django.core import serializers

import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.accounts.models import UserAccount  # noqa: E402
from apps.courses.models import Course, CourseQuestionLink, CourseTree, VariantTask  # noqa: E402
from apps.papers.models import ExamPaper  # noqa: E402
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption  # noqa: E402
from apps.study.models import QuestionTag, QuestionTagRelation  # noqa: E402


PACKAGE_ID = "TF_2023_T3_G9_PHYSICS_0CF24731"
COURSE_NAME = "九年级物理秋季班课件练习"
TAG_NAME = "9年级秋季班课件练习"


def fixture(queryset):
    return json.loads(serializers.serialize("json", queryset))


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/export_g9_autumn_migration.py OUTPUT.json")
    output = Path(sys.argv[1]).resolve()
    paper = ExamPaper.objects.get(source_package_id=PACKAGE_ID)
    questions = ExamQuestion.objects.filter(paper=paper).order_by("sort_order", "id")
    course = Course.objects.get(name=COURSE_NAME, is_deleted=False)
    tag = QuestionTag.objects.get(name=TAG_NAME)
    teacher = UserAccount.objects.get(pk=course.teacher_id)

    payload = {
        "meta": {
            "package_id": PACKAGE_ID,
            "paper_id": str(paper.id),
            "course_id": str(course.id),
            "tag_id": str(tag.id),
            "teacher_id": str(teacher.id),
            "teacher_mobile": teacher.mobile,
            "source_sha256": paper.source_sha256,
            "media_dir": f"exams/json_imports/{paper.id}",
        },
        "papers": fixture(ExamPaper.objects.filter(pk=paper.pk)),
        "questions": fixture(questions),
        "options": fixture(QuestionOption.objects.filter(question__in=questions).order_by("question_id", "sort_order", "id")),
        "images": fixture(QuestionImage.objects.filter(question__in=questions).order_by("question_id", "image_type", "sort_order", "id")),
        "courses": fixture(Course.objects.filter(pk=course.pk)),
        "trees": fixture(CourseTree.objects.filter(course=course).order_by("sort_order", "id")),
        "course_links": fixture(CourseQuestionLink.objects.filter(course=course).order_by("id")),
        "tags": fixture(QuestionTag.objects.filter(pk=tag.pk)),
        "tag_relations": fixture(QuestionTagRelation.objects.filter(tag=tag, question__in=questions).order_by("question_id", "id")),
        "variant_tasks": fixture(VariantTask.objects.filter(original_question__in=questions).order_by("id")),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({key: len(value) for key, value in payload.items() if isinstance(value, list)}, ensure_ascii=False))
    print(f"wrote {output} ({output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
