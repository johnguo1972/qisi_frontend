import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import StudentParentBind, UserAccount
from apps.study.models import AnswerAttempt


@pytest.mark.django_db
def test_student_can_start_and_submit_draft_attempt(student_client, sample_question, sample_mission_level):
    start = student_client.post(
        '/api/v1/student/attempts/start',
        {'question_id': str(sample_question.id), 'level_id': str(sample_mission_level.id)},
        format='json',
    )
    assert start.status_code == 200
    attempt_id = start.data['data']['attempt_id']
    attempt = AnswerAttempt.objects.get(pk=attempt_id)
    assert attempt.submit_source == 'draft'

    submit = student_client.post(
        f'/api/v1/student/attempts/{attempt_id}/submit',
        {'answer_content': {'selected_options': ['A']}},
        format='json',
    )
    assert submit.status_code == 200
    assert submit.data['data']['attempt_id'] == attempt_id
    attempt.refresh_from_db()
    assert attempt.submit_source == 'manual'
    assert attempt.answer_content == {'selected_options': ['A']}


@pytest.mark.django_db
def test_student_cannot_submit_another_students_attempt(student_client, teacher_user, sample_question):
    attempt = AnswerAttempt.objects.create(
        student_user_id=teacher_user,
        question_id=sample_question.id,
        answer_content={},
        is_subjective_pending=True,
        submit_source='draft',
    )
    response = student_client.post(
        f'/api/v1/student/attempts/{attempt.id}/submit',
        {'answer_content': {'text': 'test'}},
        format='json',
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_parent_context_cannot_create_attempt_for_bound_child(student_user, sample_question):
    parent = UserAccount.objects.create(role_type='parent', mobile='13900000999', display_name='parent')
    StudentParentBind.objects.create(
        parent_user_id=parent,
        student_user_id=student_user,
        relation_type='guardian',
        bind_status='active',
    )
    cache.set(f'parent_context:{parent.id}', str(student_user.id), timeout=600)
    client = APIClient()
    client.force_authenticate(user=parent)
    response = client.post(
        '/api/v1/student/attempts/start',
        {'question_id': str(sample_question.id)},
        format='json',
    )
    assert response.status_code == 403
    assert response.data['code'] == 'PARENT_READ_ONLY'
    assert response.data['message'] == '家长端仅支持查看，不能代替学生答题'
    assert not AnswerAttempt.objects.filter(student_user_id=student_user, question_id=sample_question.id).exists()
