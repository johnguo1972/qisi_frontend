import pytest
from unittest.mock import Mock

from apps.accounts.models import UserAccount
from apps.common.ai.exceptions import AIResponseError
from apps.courses.models import Course
from apps.study import document_import_tasks as module
from apps.study.document_import_models import QuestionDocumentImportTask
from apps.study.document_import_service import ExtractedDocument, ExtractedQuestionFragment
from apps.study.models import QuestionIngestionBatch


def valid_question():
    return {
        'question_no': '1',
        'question_type': 'single_choice',
        'stem': 'Choose one.',
        'options': [{'label': 'A', 'content': 'One'}],
        'answer': 'A',
        'analysis': 'Only A is one.',
        'tables': [],
        'illustrations': [],
        'confidence': 0.9,
        'review_reason': '',
        'source': {'page_start': 1, 'page_end': 1},
    }


@pytest.fixture
def task(db):
    teacher = UserAccount.objects.create(
        mobile='13900008302', display_name='Document task teacher', role_type='teacher',
    )
    course = Course.objects.create(
        name='Document task course', subject='math', grade_level='Grade 8', teacher=teacher,
    )
    batch = QuestionIngestionBatch.objects.create(
        actor=teacher,
        course=course,
        source_type=QuestionIngestionBatch.SourceType.DOCUMENT_IMPORT,
        source_name='questions.pdf',
    )
    return QuestionDocumentImportTask.objects.create(
        batch=batch,
        course=course,
        source_file='imports/questions.pdf',
        detected_mime='application/pdf',
        document_type='pdf',
        page_count=2,
    )


@pytest.mark.django_db
def test_task_marks_partial_success_after_one_candidate_failure(task, monkeypatch):
    """One malformed Qwen candidate never prevents a valid sibling from importing."""
    monkeypatch.setattr(
        module,
        'extract_document',
        lambda _path: ExtractedDocument(
            document_type='pdf', page_count=2,
            fragments=[
                ExtractedQuestionFragment(question_no='1', text='1. Choose one.'),
                ExtractedQuestionFragment(question_no='2', text='2. Broken candidate.'),
            ],
        ),
    )
    monkeypatch.setattr(
        module,
        'structure_candidate',
        Mock(side_effect=[valid_question(), AIResponseError('bad json')]),
    )

    module.process_document_import_task.run(str(task.id))

    task.refresh_from_db()
    assert task.stage == 'partial_success'
