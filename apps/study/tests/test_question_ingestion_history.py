from datetime import timedelta
import json
from io import BytesIO
import uuid
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.courses.models import Course
from apps.parser.models import ExamQuestion
from apps.study.ingestion import finish_ingestion_batch, start_ingestion_batch
from apps.study.models import QuestionIngestionBatch


@pytest.fixture
def teacher(db):
    return UserAccount.objects.create(
        mobile='13900009101',
        display_name='Ingestion history teacher',
        role_type='teacher',
    )


@pytest.fixture
def other_teacher(db):
    return UserAccount.objects.create(
        mobile='13900009102',
        display_name='Other ingestion history teacher',
        role_type='teacher',
    )


@pytest.fixture
def api_client(teacher):
    client = APIClient()
    client.force_authenticate(user=teacher)
    return client


@pytest.fixture
def other_course(other_teacher):
    return Course.objects.create(
        name='Other teacher course',
        subject='physics',
        grade_level='Grade 8',
        teacher=other_teacher,
    )


@pytest.mark.django_db
def test_bank_history_returns_only_current_actor_recent_rows(api_client, teacher, other_teacher):
    expected = QuestionIngestionBatch.objects.create(
        actor=teacher,
        source_type='manual_create',
        source_name='Manual question',
        created_count=1,
    )
    QuestionIngestionBatch.objects.create(
        actor=other_teacher,
        source_type='manual_create',
        source_name='Other teacher question',
        created_count=1,
    )
    stale = QuestionIngestionBatch.objects.create(
        actor=teacher,
        source_type='manual_create',
        source_name='Old question',
        created_count=1,
    )
    QuestionIngestionBatch.objects.filter(pk=stale.pk).update(
        created_at=timezone.now() - timedelta(days=31),
    )

    response = api_client.get('/api/v1/questions/ingestion-history/?scope=bank')

    assert response.status_code == 200
    assert [item['id'] for item in response.data['data']['items']] == [str(expected.id)]


@pytest.mark.django_db
def test_course_history_for_foreign_course_is_forbidden(api_client, other_course):
    response = api_client.get(
        f'/api/v1/questions/ingestion-history/?scope=course&course_id={other_course.id}',
    )

    assert response.status_code == 403
    assert response.data['code'] == 403
    assert response.data['data'] is None
    assert response.data['message']
    assert response.data['trace_id']


@pytest.mark.django_db
@pytest.mark.parametrize('url', [
    '/api/v1/questions/ingestion-history/?scope=unsupported',
    '/api/v1/questions/ingestion-history/?scope=course',
])
def test_invalid_history_query_uses_project_error_envelope(api_client, url):
    response = api_client.get(url)

    assert response.status_code == 400
    assert response.data['code'] == 400
    assert response.data['data'] is None
    assert response.data['message']
    assert response.data['trace_id']


@pytest.mark.django_db
def test_malformed_course_id_uses_project_error_envelope(api_client):
    response = api_client.get(
        '/api/v1/questions/ingestion-history/?scope=course&course_id=not-a-uuid',
    )

    assert response.status_code == 400
    assert response.data['code'] == 400
    assert response.data['data'] is None
    assert response.data['message']
    assert response.data['trace_id']


@pytest.mark.django_db
def test_missing_course_uses_project_not_found_envelope(api_client):
    response = api_client.get(
        f'/api/v1/questions/ingestion-history/?scope=course&course_id={uuid.uuid4()}',
    )

    assert response.status_code == 404
    assert response.data['code'] == 404
    assert response.data['data'] is None
    assert response.data['message']
    assert response.data['trace_id']


@pytest.mark.django_db
def test_all_duplicate_import_has_visible_zero_created_batch(teacher):
    batch = start_ingestion_batch(
        actor=teacher,
        source_type='json_import',
        source_name='duplicate-package.zip',
    )

    finish_ingestion_batch(
        batch,
        total_read=2,
        created_count=0,
        skipped_existing_count=2,
        skipped_in_package_count=0,
        failed_count=0,
    )

    batch.refresh_from_db()
    assert batch.status == 'success'
    assert batch.created_count == 0


@pytest.mark.django_db
def test_batch_with_failures_and_completed_questions_is_partial_success(teacher):
    batch = start_ingestion_batch(
        actor=teacher,
        source_type='json_import',
        source_name='partially-imported.zip',
    )

    finish_ingestion_batch(
        batch,
        total_read=3,
        created_count=1,
        skipped_existing_count=1,
        skipped_in_package_count=0,
        failed_count=1,
    )

    batch.refresh_from_db()
    assert batch.status == 'partial_success'
    assert batch.created_count == 1
    assert batch.skipped_existing_count == 1
    assert batch.failed_count == 1
    assert batch.finished_at is not None


@pytest.mark.django_db
def test_batch_with_only_failures_is_failed(teacher):
    batch = start_ingestion_batch(
        actor=teacher,
        source_type='json_import',
        source_name='failed.zip',
    )

    finish_ingestion_batch(
        batch,
        total_read=2,
        created_count=0,
        skipped_existing_count=0,
        skipped_in_package_count=0,
        failed_count=2,
    )

    batch.refresh_from_db()
    assert batch.status == 'failed'
    assert batch.total_read == 2
    assert batch.failed_count == 2
    assert batch.finished_at is not None


@pytest.mark.django_db
def test_successful_json_import_is_visible_in_actor_history_with_canonical_type(
    api_client, teacher, tmp_path, settings
):
    """Catch regressions that disconnect JSON import, type normalization, and audit history."""
    settings.MEDIA_ROOT = tmp_path / 'media'
    package = {
        'paper': {
            'title': 'Integrated ingestion history',
            'subject': 'math',
            'grade': 'Grade 8',
        },
        'questions': [{
            'question_no': '1',
            'question_type': 'calculation',
            'stem': 'Calculate 6 * 7.',
            'answer': {'raw': '42'},
        }],
    }
    archive = BytesIO()
    with zipfile.ZipFile(archive, 'w') as package_zip:
        package_zip.writestr(
            'all_questions.json',
            json.dumps(package, ensure_ascii=False),
        )

    import_response = api_client.post(
        '/api/v1/questions/import-json-package',
        {
            'file': SimpleUploadedFile(
                'integrated-history.zip',
                archive.getvalue(),
                'application/zip',
            ),
        },
        format='multipart',
    )

    assert import_response.status_code == 200
    assert import_response.data['data']['total_read'] == 1
    assert import_response.data['data']['imported'] == 1
    question = ExamQuestion.objects.get()
    assert question.question_type == 'computation'

    history_response = api_client.get(
        '/api/v1/questions/ingestion-history/?scope=bank',
    )
    batch = QuestionIngestionBatch.objects.get(actor=teacher)

    assert history_response.status_code == 200
    assert history_response.data['code'] == 0
    assert history_response.data['data']['items'] == [{
        'id': str(batch.id),
        'source_type': 'json_import',
        'source_name': 'integrated-history.zip',
        'status': 'success',
        'course_id': None,
        'paper_id': import_response.data['data']['paper_id'],
        'total_read': 1,
        'created_count': 1,
        'skipped_existing_count': 0,
        'skipped_in_package_count': 0,
        'failed_count': 0,
        'started_at': batch.started_at,
        'finished_at': batch.finished_at,
        'created_at': batch.created_at,
    }]
