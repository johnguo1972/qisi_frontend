import io

import pytest
from PIL import Image
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.models import UserAccount
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
