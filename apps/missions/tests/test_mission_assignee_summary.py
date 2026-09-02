import pytest

from apps.accounts.models import UserAccount
from apps.institutions.models import Class, ClassStudent, Institution
from apps.missions.models import LearningMission, MissionClassAssignment
from apps.missions.serializers import MissionListSerializer
from apps.missions.wrongbook_matrix import _mission_name


@pytest.mark.django_db
def test_mission_list_describes_full_class_and_named_students_and_wrongbook_name():
    teacher = UserAccount.objects.create(
        role_type='teacher', mobile='13900000881', display_name='Teacher', password='x',
    )
    named_student = UserAccount.objects.create(
        role_type='student', mobile='13900000882', login_name='user9181', display_name='User9181', password='x',
    )
    other_student = UserAccount.objects.create(
        role_type='student', mobile='13900000883', login_name='user9182', display_name='User9182', password='x',
    )
    institution = Institution.objects.create(institution_name='summary institution', created_by=teacher)
    class_obj = Class.objects.create(institution=institution, creator_teacher=teacher, class_name='精英2班')
    ClassStudent.objects.create(class_obj=class_obj, student=named_student, join_type='manual', status='active')
    ClassStudent.objects.create(class_obj=class_obj, student=other_student, join_type='manual', status='active')

    full_class = LearningMission.objects.create(
        creator_teacher_id=teacher, class_obj=class_obj, mission_name='全班作业', status='published',
    )
    MissionClassAssignment.objects.create(mission=full_class, class_obj=class_obj, status='active')
    named_only = LearningMission.objects.create(
        creator_teacher_id=teacher, class_obj=class_obj, mission_name='个人作业', status='published',
        target_student_ids=[str(named_student.id)],
    )
    MissionClassAssignment.objects.create(
        mission=named_only, class_obj=class_obj, status='active', target_student_ids=[str(named_student.id)],
    )

    assert MissionListSerializer(full_class).data['assignment_summary'] == '全班：精英2班'
    assert MissionListSerializer(named_only).data['assignment_summary'] == '指定学生：User9181（user9181）'
    assert _mission_name(named_only, target_students=[str(named_student.id)]).endswith('-User9181')
