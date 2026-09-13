import pytest

from apps.accounts.models import UserAccount
from apps.courses.models import Course, CourseQuestionLink
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, QuestionContentFingerprint
from apps.parser.question_identity import build_content_fingerprint
from apps.study.models import QuestionIngestionBatch
from apps.study.structured_ingestion import ingest_structured_questions


@pytest.fixture
def teacher(db):
    return UserAccount.objects.create(
        mobile='13900008301', display_name='Structured import teacher', role_type='teacher',
    )


@pytest.fixture
def course(teacher):
    return Course.objects.create(
        name='Structured import course', subject='math', grade_level='Grade 8', teacher=teacher,
    )


def make_batch(teacher, course):
    return QuestionIngestionBatch.objects.create(
        actor=teacher,
        course=course,
        source_type=QuestionIngestionBatch.SourceType.DOCUMENT_IMPORT,
        source_name='questions.pdf',
    )


@pytest.fixture
def structured_question():
    return {
        'question_no': '1',
        'question_type': 'single_choice',
        'stem': 'Which number is one?',
        'options': [{'label': 'A', 'content': 'One'}],
        'answer': 'A',
        'analysis': 'One is the answer.',
        'tables': [],
        'illustrations': [],
        'confidence': 0.95,
        'review_reason': '',
        'source': {'page_start': 1, 'page_end': 1},
    }


@pytest.fixture
def existing_question(teacher, structured_question):
    paper = ExamPaper.objects.create(title='Existing questions', subject='math', uploaded_by=teacher)
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no='1',
        question_type='single_choice',
        subject='math',
        stem=structured_question['stem'],
    )
    fingerprint = build_content_fingerprint(
        stem=structured_question['stem'], options=['One'], formula_texts=[], image_hashes=[],
    )
    QuestionContentFingerprint.objects.create(
        fingerprint=fingerprint,
        canonical_question=question,
        state=QuestionContentFingerprint.State.ACTIVE,
    )
    return question


@pytest.mark.django_db
def test_existing_question_is_linked_without_recreation(
    teacher, course, existing_question, structured_question,
):
    """An existing canonical question is linked to the course rather than duplicated."""
    result = ingest_structured_questions(
        questions=[structured_question], paper_info={'title': 'paper'}, actor=teacher,
        batch=make_batch(teacher, course), source_root=None, course=course, tree_node=None,
    )

    assert result.imported == 0
    assert result.skipped_existing == 1
    assert CourseQuestionLink.objects.filter(course=course, question=existing_question).exists()
