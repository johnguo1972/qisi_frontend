import io

import pytest
from PIL import Image
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount
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


@pytest.mark.django_db
def test_paper_entry_and_teacher_pdf():
    teacher = _user('teacher', '13900000001')
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

    request = factory.get('/api/v1/paper-pdf')
    force_authenticate(request, user=teacher)
    response = views.mission_paper_pdf(request, mission.id)
    assert response.status_code == 200
    assert response['Content-Type'] == 'application/pdf'
    assert response.content.startswith(b'%PDF')
