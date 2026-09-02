import pytest
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.courses.models import Course
from apps.institutions.models import Class, ClassTeacher, Institution


pytestmark = pytest.mark.django_db


def _teacher_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {generate_tokens(user, 'teacher')['access_token']}"
    )
    return client


def test_teacher_can_assign_accessible_course_to_owned_class_in_another_institution():
    teacher = UserAccount.objects.create(
        mobile='13921110001',
        login_name='13921110001',
        display_name='Assigning teacher',
        role_type='teacher',
        stages=['初中'],
    )
    grant_user_role(teacher, 'teacher')
    class_institution = Institution.objects.create(
        institution_name='Class institution', created_by=teacher,
    )
    class_obj = Class.objects.create(
        institution=class_institution,
        class_name='Owned class',
        creator_teacher=teacher,
    )
    ClassTeacher.objects.create(class_obj=class_obj, teacher=teacher, role='owner')

    course_owner = UserAccount.objects.create(
        mobile='13921110002',
        login_name='13921110002',
        display_name='Course owner',
        role_type='teacher',
    )
    grant_user_role(course_owner, 'teacher')
    course_institution = Institution.objects.create(
        institution_name='Course institution', created_by=course_owner,
    )
    course = Course.objects.create(
        name='Shared course',
        subject='physics',
        grade_level='九年级',
        teacher=course_owner,
        institution=course_institution,
    )

    response = _teacher_client(teacher).post(
        '/api/v1/missions/',
        {
            'mission_name': 'Cross institution assignment',
            'class_id': str(class_obj.id),
            'class_ids': [str(class_obj.id)],
            'course_id': str(course.id),
        },
        format='json',
    )

    assert response.status_code == 201
    assert response.data['data']['class_ids'] == [str(class_obj.id)]
