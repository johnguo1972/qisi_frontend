from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.courses.models import Course, CourseTree
from apps.study.document_import_models import QuestionDocumentImportTask
from apps.study.document_import_service import ValidatedDocument


@pytest.fixture
def teacher(db):
    return UserAccount.objects.create(
        mobile='13900009991', display_name='Document import teacher', role_type='teacher',
    )


@pytest.fixture
def client(teacher):
    client = APIClient()
    client.force_authenticate(user=teacher)
    return client


@pytest.fixture
def course(teacher):
    return Course.objects.create(
        name='Document import course', subject='physics', grade_level='Grade 9', teacher=teacher,
    )


@pytest.mark.django_db(transaction=True)
def test_course_document_upload_creates_persistent_task_and_dispatches(client, course, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / 'media'
    upload = SimpleUploadedFile('paper.pdf', b'%PDF-1.4\n% minimal', content_type='application/pdf')

    validated = ValidatedDocument(
        filename='paper.pdf', document_type='pdf', detected_mime='application/pdf',
        size_bytes=len(upload.read()), page_count=1,
    )
    upload.seek(0)
    node = CourseTree.objects.create(course=course, name='Chapter one', sort_order=1)
    with patch('apps.study.document_import_views.validate_document_upload', return_value=validated):
        with patch('apps.study.document_import_views.process_document_import_task.delay') as delay:
            response = client.post(
                f'/api/v1/courses/{course.id}/questions/import-document/',
                {'file': upload, 'tree_node_id': str(node.id)}, format='multipart',
            )

    assert response.status_code == 202
    assert response.data['data']['course_id'] == str(course.id)
    task = QuestionDocumentImportTask.objects.get(id=response.data['data']['task_id'])
    assert task.stage == QuestionDocumentImportTask.Stage.QUEUED
    assert task.tree_node_id == node.id
    assert response.data['data']['tree_node_id'] == str(node.id)
    assert task.source_file.startswith('course_document_imports/')
    delay.assert_called_once_with(str(task.id))


@pytest.mark.django_db
def test_course_document_status_is_hidden_from_another_course(client, course, teacher):
    other_course = Course.objects.create(
        name='Other document course', subject='physics', grade_level='Grade 9', teacher=teacher,
    )
    from apps.study.ingestion import start_ingestion_batch

    batch = start_ingestion_batch(
        actor=teacher, source_type='document_import', source_name='paper.pdf', course=course,
    )
    task = QuestionDocumentImportTask.objects.create(
        batch=batch, course=course, source_file='course_document_imports/paper.pdf',
        detected_mime='application/pdf', document_type='pdf', page_count=1,
    )

    response = client.get(
        f'/api/v1/courses/{other_course.id}/questions/import-document/{task.id}/status/'
    )

    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_course_document_upload_persists_failed_dispatch_instead_of_returning_500(client, course, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / 'media'
    upload = SimpleUploadedFile('paper.pdf', b'%PDF-1.4\n% minimal', content_type='application/pdf')
    validated = ValidatedDocument(
        filename='paper.pdf', document_type='pdf', detected_mime='application/pdf',
        size_bytes=len(upload.read()), page_count=1,
    )
    upload.seek(0)
    with patch('apps.study.document_import_views.validate_document_upload', return_value=validated):
        with patch('apps.study.document_import_views.process_document_import_task.delay', side_effect=RuntimeError('broker unavailable')):
            response = client.post(
                f'/api/v1/courses/{course.id}/questions/import-document/', {'file': upload}, format='multipart',
            )

    assert response.status_code == 202
    task = QuestionDocumentImportTask.objects.get(id=response.data['data']['task_id'])
    assert task.stage == QuestionDocumentImportTask.Stage.FAILED
    assert 'broker unavailable' not in task.error_summary
