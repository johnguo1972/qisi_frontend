import hashlib

import pytest

from apps.accounts.models import UserAccount
from apps.courses.models import Course, CourseQuestionLink
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, QuestionContentFingerprint, QuestionImage
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


@pytest.mark.django_db
def test_asset_preflight_retries_one_transient_read_error(tmp_path, teacher, course, monkeypatch):
    """A transient source-image read failure must not discard an otherwise valid question."""
    asset_path = tmp_path / 'diagram.png'
    asset_path.write_bytes(b'diagram-bytes')
    question = {
        'question_no': '2', 'question_type': 'single_choice', 'stem': 'Read the diagram.',
        'options': [{'label': 'A', 'content': 'One'}], 'answer': 'A',
        'illustrations': [{'file': 'diagram.png'}],
    }
    original_read_bytes = type(asset_path).read_bytes
    attempts = {'count': 0}

    def read_bytes(path):
        if path == asset_path and attempts['count'] == 0:
            attempts['count'] += 1
            raise OSError('temporary asset read failure')
        attempts['count'] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(type(asset_path), 'read_bytes', read_bytes)
    result = ingest_structured_questions(
        questions=[question], paper_info={'title': 'retry'}, actor=teacher,
        batch=make_batch(teacher, course), source_root=tmp_path, course=course, tree_node=None,
    )

    assert result.imported == 1
    assert result.failed == 0
    assert attempts['count'] == 2


@pytest.mark.django_db
def test_existing_question_backfills_document_illustration_once(
    tmp_path, teacher, course, existing_question, structured_question,
):
    asset_path = tmp_path / 'diagram.png'
    asset_path.write_bytes(b'diagram-bytes')
    question = {
        **structured_question,
        'illustrations': [{'file': 'diagram.png', 'placement': 'stem'}],
    }
    fingerprint = build_content_fingerprint(
        stem=structured_question['stem'], options=['One'], formula_texts=[],
        image_hashes=[hashlib.sha256(asset_path.read_bytes()).hexdigest()],
    )
    QuestionContentFingerprint.objects.filter(
        canonical_question=existing_question,
    ).update(fingerprint=fingerprint)

    first = ingest_structured_questions(
        questions=[question], paper_info={'title': 'backfill'}, actor=teacher,
        batch=make_batch(teacher, course), source_root=tmp_path, course=course, tree_node=None,
    )
    second = ingest_structured_questions(
        questions=[question], paper_info={'title': 'backfill'}, actor=teacher,
        batch=make_batch(teacher, course), source_root=tmp_path, course=course, tree_node=None,
    )

    assert first.skipped_existing == 1
    assert second.skipped_existing == 1
    assert QuestionImage.objects.filter(question=existing_question).count() == 1
