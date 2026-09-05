from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.courses.models import Course
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
