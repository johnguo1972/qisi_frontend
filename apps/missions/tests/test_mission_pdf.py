import pytest
from django.core.cache import cache
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.institutions.models import Class, ClassStudent, Institution
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.missions import views
from apps.parser.models import ExamPaper, ExamQuestion


def _user(role, mobile):
    return UserAccount.objects.create(
        role_type=role, mobile=mobile, login_name=mobile, display_name=role,
    )


def _client(user, role):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {generate_tokens(user, role)['access_token']}"
    )
    return client


@pytest.mark.django_db
def test_publish_generates_ordered_pdf_and_student_parent_lists_expose_it(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'MEDIA_ROOT', str(tmp_path))
    teacher = _user('teacher', '13900000801')
    grant_user_role(teacher, 'teacher')
    student_parent = _user('student', '13900000802')
    grant_user_role(student_parent, 'student')
    grant_user_role(student_parent, 'parent')

    institution = Institution.objects.create(
        institution_name='PDF Test Institution', created_by=teacher,
    )
    class_obj = Class.objects.create(
        institution=institution, creator_teacher=teacher, class_name='PDF Test Class',
    )
    ClassStudent.objects.create(
        class_obj=class_obj, student=student_parent, join_type='manual', status='active',
    )
    paper = ExamPaper.objects.create(
        title='PDF Test Paper', subject='physics', source_file_path='test.pdf',
    )
    short_answer = ExamQuestion.objects.create(
        paper=paper, question_no='2', question_type='short_answer', stem='简答题',
    )
    choice = ExamQuestion.objects.create(
        paper=paper, question_no='1', question_type='single_choice', stem='选择题',
    )
    mission = LearningMission.objects.create(
        creator_teacher_id=teacher, class_obj=class_obj,
        mission_name='PDF 作业', status='draft', assignment_mode='flat',
        end_at='2026-09-20T23:59:59+08:00',
    )
    level = MissionLevel.objects.create(
        mission=mission, level_no=1, level_name='作业题目', level_type='practice',
    )
    # Deliberately store the choice after the short answer in the relation
    # table; publication now uses the natural numeric question order.
    MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=short_answer.id, sort_no=1,
    )
    MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=choice.id, sort_no=2,
    )

    captured = {}

    def fake_build_pdf(export_type, questions, include_answers, watermark_text=''):
        captured['questions'] = questions
        return b'%PDF-published'

    monkeypatch.setattr('apps.study.student_views._build_pdf', fake_build_pdf)

    response = _client(teacher, 'teacher').post(
        f'/api/v1/missions/{mission.id}/publish'
    )
    assert response.status_code == 200
    mission.refresh_from_db()
    assert mission.status == 'published'
    assert mission.pdf_file_path.endswith(f'mission_{mission.id}.pdf')
    assert [question['question_no'] for question in captured['questions']] == ['1', '2']

    student_response = _client(student_parent, 'student').get('/api/v1/student/home')
    assert student_response.status_code == 200
    assert student_response.data['data']['missions'][0]['pdf_download_url'].endswith(
        mission.pdf_file_path
    )

    cache.set(f'parent_context:{student_parent.id}', str(student_parent.id), timeout=600)
    parent_response = _client(student_parent, 'parent').get('/api/v1/parent/missions')
    assert parent_response.status_code == 200
    assert parent_response.data['data']['missions'][0]['pdf_download_url'].endswith(
        mission.pdf_file_path
    )
    cache.clear()
