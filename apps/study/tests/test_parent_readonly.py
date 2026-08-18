import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import StudentParentBind, UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.institutions.models import Class, ClassStudent, Institution
from apps.missions.models import LearningMission, MissionLevel
from apps.study.models import StudentMissionProgress


@pytest.mark.django_db
def test_parent_mission_queries_are_read_only():
    student_user = UserAccount.objects.create(
        role_type='student', mobile='13900000992', display_name='测试学生',
    )
    grant_user_role(student_user, 'student')
    parent = UserAccount.objects.create(
        role_type='parent', mobile='13900000991', display_name='测试家长',
    )
    grant_user_role(parent, 'parent')
    institution = Institution.objects.create(
        institution_name='只读测试机构', created_by=student_user,
    )
    class_obj = Class.objects.create(
        institution=institution, creator_teacher=student_user, class_name='只读测试班',
    )
    ClassStudent.objects.create(
        class_obj=class_obj, student=student_user, join_type='manual', status='active',
    )
    mission = LearningMission.objects.create(
        class_obj=class_obj, creator_teacher_id=student_user,
        mission_name='只读任务', status='published',
    )
    MissionLevel.objects.create(
        mission=mission, level_no=1, level_name='第一关', level_type='practice',
    )
    StudentParentBind.objects.create(
        parent_user_id=parent, student_user_id=student_user,
        relation_type='guardian', bind_status='active',
    )
    cache.set(f'parent_context:{parent.id}', str(student_user.id), timeout=600)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(parent, 'parent')['access_token']}")
    before = StudentMissionProgress.objects.count()

    overview = client.get('/api/v1/parent/overview')
    missions = client.get('/api/v1/parent/missions')
    detail = client.get(f'/api/v1/parent/missions/{mission.id}')

    assert overview.status_code == 200
    assert missions.status_code == 200
    assert detail.status_code == 200
    assert missions.data['data']['missions'][0]['id'] == mission.id
    assert detail.data['data']['mission']['levels'][0]['question_count'] == 0
    assert StudentMissionProgress.objects.count() == before
    cache.clear()
