"""Create the course, lesson nodes, course links and tag for the import."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.courses.models import Course, CourseQuestionLink, CourseTree
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion
from apps.study.models import QuestionTag, QuestionTagRelation


TAG_NAME = "9\u5e74\u7ea7\u79cb\u5b63\u73ed\u8bfe\u4ef6\u7ec3\u4e60"
COURSE_NAME = "\u4e5d\u5e74\u7ea7\u7269\u7406\u79cb\u5b63\u73ed\u8bfe\u4ef6\u7ec3\u4e60"


class Command(BaseCommand):
    help = "Publish imported Grade 9 autumn questions into a course and searchable tag."

    def add_arguments(self, parser):
        parser.add_argument("--paper-id", required=True)
        parser.add_argument("--teacher-id", required=True)
        parser.add_argument("--course-name", default=COURSE_NAME)
        parser.add_argument("--tag-name", default=TAG_NAME)

    def handle(self, *args, **opts):
        from apps.accounts.models import UserAccount

        try:
            teacher = UserAccount.objects.get(id=opts["teacher_id"], role_type="teacher")
            paper = ExamPaper.objects.get(id=opts["paper_id"], source_package_id__isnull=False)
        except (UserAccount.DoesNotExist, ExamPaper.DoesNotExist) as exc:
            raise CommandError("teacher or imported paper not found") from exc

        questions = list(ExamQuestion.objects.filter(paper=paper).order_by("sort_order", "id"))
        if len(questions) != 277:
            raise CommandError(f"expected 277 imported questions, got {len(questions)}")
        question_ids = {question.id for question in questions}
        existing_course = Course.objects.filter(
            name=opts["course_name"], teacher=teacher, is_deleted=False
        ).first()
        if existing_course:
            existing_links = CourseQuestionLink.objects.filter(
                course=existing_course, is_deleted=False
            )
            outside_links = existing_links.exclude(question_id__in=question_ids).exists()
            if outside_links or existing_links.count() not in (0, 277):
                raise CommandError(
                    "same-name course already contains unrelated or partial questions; "
                    "review it before publishing"
                )
        existing_tag = QuestionTag.objects.filter(name=opts["tag_name"]).first()
        if existing_tag:
            outside_tag_relations = QuestionTagRelation.objects.filter(tag=existing_tag).exclude(
                question_id__in=question_ids
            ).exists()
            if outside_tag_relations:
                raise CommandError(
                    "tag already belongs to unrelated questions; use a new tag name"
                )

        with transaction.atomic():
            course, _ = Course.objects.get_or_create(
                name=opts["course_name"], teacher=teacher, is_deleted=False,
                defaults={
                    "description": "\u4e5d\u5e74\u7ea7\u7269\u7406\u79cb\u5b63\u73ed\u8bfe\u4ef6\u7ec3\u4e60\uff1b\u7b54\u6848\u548c\u89e3\u6790\u5f85\u8865\u5145\u3002",
                    "subject": "\u7269\u7406", "grade_level": "\u4e5d\u5e74\u7ea7",
                },
            )
            names = []
            for question in questions:
                name = (question.section_title or "未分讲次").split("/", 1)[0].strip()
                if name not in names:
                    names.append(name)
            nodes = {}
            for order, name in enumerate(names, 1):
                node, _ = CourseTree.objects.get_or_create(
                    course=course, parent=None, name=name,
                    defaults={"sort_order": order},
                )
                node.sort_order = order
                node.save(update_fields=["sort_order"])
                nodes[name] = node
            for question in questions:
                name = (question.section_title or "未分讲次").split("/", 1)[0].strip()
                CourseQuestionLink.objects.update_or_create(
                    course=course, question=question,
                    defaults={
                        "tree_node": nodes[name], "source": "import",
                        "source_course_name": course.name, "is_deleted": False,
                    },
                )
            tag, _ = QuestionTag.objects.get_or_create(
                name=opts["tag_name"],
                defaults={"color": "#e67e22", "created_by": teacher},
            )
            for question in questions:
                QuestionTagRelation.objects.get_or_create(question=question, tag=tag)
            for question in questions:
                names_for_question = list(
                    QuestionTagRelation.objects.filter(question=question)
                    .select_related("tag").values_list("tag__name", flat=True)
                )
                ExamQuestion.objects.filter(id=question.id).update(tags=names_for_question)
            tag.question_count = QuestionTagRelation.objects.filter(tag=tag).count()
            tag.save(update_fields=["question_count"])

        self.stdout.write(self.style.SUCCESS(str({
            "course_id": str(course.id), "tag_id": str(tag.id),
            "questions": len(questions), "course_links": CourseQuestionLink.objects.filter(
                course=course, is_deleted=False).count(),
            "nodes": CourseTree.objects.filter(course=course).count(),
            "tag_relations": QuestionTagRelation.objects.filter(tag=tag).count(),
            "tag_question_count": tag.question_count,
        })))
