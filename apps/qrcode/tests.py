import io

import pytest
from PIL import Image
from django.core.cache import cache
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.models import StudentParentBind, UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.institutions.models import Class, ClassStudent, Institution
from apps.missions.models import LearningMission
from apps.qrcode import views
from apps.qrcode.services import analyze_image_blur, ensure_mission_short_code, ensure_student_short_code


def _user(role, mobile):
    return UserAccount.objects.create(role_type=role, mobile=mobile, login_name=mobile, display_name=role)


@pytest.mark.django_db
def test_blur_detector_rejects_flat_image():
    stream = io.BytesIO()
    Image.new('RGB', (160, 160), 'white').save(stream, format='PNG')
    stream.seek(0)
    score, blurry = analyze_image_blur(stream)
    assert score == 0
    assert blurry is True


def _client_for(user, active_role):
    token = generate_tokens(user, active_role)['access_token']
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.mark.django_db
def test_paper_entry_and_teacher_pdf(monkeypatch):
    teacher = _user('teacher', '13900000001')
    grant_user_role(teacher, 'teacher')
    grant_user_role(teacher, 'student')
    student = _user('student', '13900000002')
    institution = Institution.objects.create(institution_name='QR Test', created_by=teacher)
    class_obj = Class.objects.create(institution=institution, creator_teacher=teacher, class_name='QR Class')
    ClassStudent.objects.create(class_obj=class_obj, student=student, join_type='invite', status='active')
    mission = LearningMission.objects.create(creator_teacher_id=teacher, class_obj=class_obj, mission_name='QR Mission', status='published')
    mission_code = ensure_mission_short_code(mission)
    student_code = ensure_student_short_code(student, class_obj)
    factory = APIRequestFactory()

    request = factory.get('/api/v1/paper')
    response = views.paper_entry(request, student_code.short_code, mission_code.short_code, 1)
    assert response.status_code == 200
    assert response.data['data']['student_id'] == student.id

    monkeypatch.setattr(views, '_paper_pdf', lambda *args: b'%PDF-test')
    response = _client_for(teacher, 'teacher').get(
        f'/api/v1/missions/{mission.id}/paper-pdf'
    )
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    assert response.content.startswith(b'%PDF')

    response = _client_for(teacher, 'student').get(
        f'/api/v1/missions/{mission.id}/paper-pdf'
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_parent_bind_request_requires_student_confirmation_and_supports_children():
    student = _user('student', '13900000101')
    grant_user_role(student, 'student')
    parent = _user('parent', '13900000102')
    grant_user_role(parent, 'parent')

    student_client = _client_for(student, 'student')
    parent_client = _client_for(parent, 'parent')

    generated = student_client.post('/api/v1/student/parent-bind-codes')
    assert generated.status_code == 200
    assert generated.data['data']['expires_in'] == 3600
    bind_code = generated.data['data']['bind_code']

    requested = parent_client.post('/api/v1/parent/bind-requests', {
        'bind_code': bind_code,
        'relation_type': 'mother',
    })
    assert requested.status_code == 200
    bind_id = requested.data['data']['id']
    relation = StudentParentBind.objects.get(pk=bind_id)
    assert relation.bind_status == 'pending'

    assert parent_client.get('/api/v1/parent/children').data['data'] == []
    pending = student_client.get('/api/v1/student/parent-bind-requests')
    assert pending.status_code == 200
    assert pending.data['data'][0]['parent_id'] == str(parent.id)

    approved = student_client.post(
        f'/api/v1/student/parent-bind-requests/{bind_id}/decision',
        {'decision': 'approve'},
    )
    assert approved.status_code == 200
    relation.refresh_from_db()
    assert relation.bind_status == 'active'

    children = parent_client.get('/api/v1/parent/children')
    assert children.status_code == 200
    assert children.data['data'][0]['id'] == student.id

    context = parent_client.post('/api/v1/parent/context', {'student_id': str(student.id)})
    assert context.status_code == 200

    second_student = _user('student-2', '13900000103')
    grant_user_role(second_student, 'student')
    second_code_response = _client_for(second_student, 'student').post('/api/v1/student/parent-bind-codes')
    second_requested = parent_client.post('/api/v1/parent/bind-requests', {
        'bind_code': second_code_response.data['data']['bind_code'],
        'relation_type': 'guardian',
    })
    second_bind_id = second_requested.data['data']['id']
    second_approved = _client_for(second_student, 'student').post(
        f'/api/v1/student/parent-bind-requests/{second_bind_id}/decision',
        {'decision': 'approve'},
    )
    assert second_approved.status_code == 200
    child_ids = {item['id'] for item in parent_client.get('/api/v1/parent/children').data['data']}
    assert child_ids == {student.id, second_student.id}

    removed = parent_client.delete(f'/api/v1/parent/binds/{bind_id}')
    assert removed.status_code == 200
    remaining = parent_client.get('/api/v1/parent/children').data['data']
    assert [item['id'] for item in remaining] == [second_student.id]
    cache.clear()


@pytest.mark.django_db
def test_parent_cannot_bind_own_student_role():
    user = _user('student', '13900000104')
    grant_user_role(user, 'student')
    grant_user_role(user, 'parent')

    student_client = _client_for(user, 'student')
    parent_client = _client_for(user, 'parent')
    generated = student_client.post('/api/v1/student/parent-bind-codes')
    assert generated.status_code == 200

    response = parent_client.post('/api/v1/parent/bind-requests', {
        'bind_code': generated.data['data']['bind_code'],
        'relation_type': 'father',
    })
    assert response.status_code == 400
    assert response.data['code'] == 'SELF_BINDING_NOT_ALLOWED'
