import pytest

from apps.study.document_import_models import QuestionDocumentImportTask
from apps.study.models import QuestionIngestionBatch


@pytest.fixture
def teacher(db):
    from apps.accounts.models import UserAccount

    return UserAccount.objects.create(
        mobile='13900008221', display_name='Document import teacher', role_type='teacher',
    )


@pytest.fixture
def course(teacher):
    from apps.courses.models import Course

    return Course.objects.create(
        name='Document import course', subject='physics', grade_level='Grade 8', teacher=teacher,
    )


@pytest.mark.django_db
def test_document_task_starts_queued(teacher, course):
    """A newly persisted document task must be ready for extraction, not running."""
    batch = QuestionIngestionBatch.objects.create(
        actor=teacher, course=course, source_type='document_import', source_name='paper.pdf',
    )
    task = QuestionDocumentImportTask.objects.create(
        batch=batch, course=course, source_file='imports/paper.pdf',
        detected_mime='application/pdf', document_type='pdf', page_count=2,
    )

    assert task.stage == 'queued'
