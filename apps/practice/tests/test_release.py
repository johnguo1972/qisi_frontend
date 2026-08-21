from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_practice_feature_flag_can_disable_the_whole_domain(student_client):
    with override_settings(PRACTICE_FEATURE_ENABLED=False):
        response = student_client.get('/api/v1/practice/pool')
    assert response.status_code == 403


@pytest.mark.django_db
def test_practice_beta_allowlist_is_checked_against_authenticated_actor(
    student_client, student_user
):
    with override_settings(
        PRACTICE_FEATURE_ENABLED=True,
        PRACTICE_BETA_MOBILES=('13900000000',),
    ):
        denied = student_client.get('/api/v1/practice/pool')
    assert denied.status_code == 403

    with override_settings(
        PRACTICE_FEATURE_ENABLED=True,
        PRACTICE_BETA_MOBILES=(student_user.mobile,),
    ):
        allowed = student_client.get('/api/v1/practice/pool')
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_practice_health_reports_migration_and_feature_state():
    response = APIClient().get('/api/v1/practice/health')
    assert response.status_code == 200
    data = response.json()['data']
    assert data['status'] == 'ready'
    assert data['migration_ready'] is True
    assert data['database_ready'] is True
    assert 'beta_allowlist_configured' in data['feature']


@pytest.mark.django_db
def test_practice_release_check_strict_passes_when_database_is_ready():
    output = StringIO()
    with override_settings(PRACTICE_BETA_MOBILES=('13900000333',)):
        call_command('practice_release_check', '--strict', stdout=output)
    assert 'OK: 可进入下一步灰度验证' in output.getvalue()
