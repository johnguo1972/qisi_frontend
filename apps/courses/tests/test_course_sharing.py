from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.courses.models import Course
from apps.courses.views import _check_course_owner, course_list_or_create


class CourseSharingTests(TestCase):
    def setUp(self):
        self.owner = UserAccount.objects.create(
            mobile="13900001001", display_name="课程创建者", role_type="teacher",
            subject="physics", stages=["初中"],
        )
        self.peer = UserAccount.objects.create(
            mobile="13900001002", display_name="协作教师", role_type="teacher",
            subject="physics", stages=["初中"],
        )
        self.other_subject = UserAccount.objects.create(
            mobile="13900001003", display_name="数学教师", role_type="teacher",
            subject="math", stages=["初中"],
        )
        self.course = Course.objects.create(
            name="初中物理课程", subject="physics", grade_level="八年级", teacher=self.owner,
        )

    def test_administrator_role_can_access_any_shared_course(self):
        admin_teacher = UserAccount.objects.create(
            mobile="13900001004", display_name="管理员教师", role_type="teacher",
            subject="math", stages=["高中"],
        )
        grant_user_role(admin_teacher, "admin")

        _check_course_owner(self.course, admin_teacher)

    def test_same_stage_and_subject_teacher_can_list_and_edit_shared_course(self):
        request = APIRequestFactory().get("/api/v1/courses/")
        force_authenticate(request, user=self.peer)

        response = course_list_or_create(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["data"]], [str(self.course.id)])
        _check_course_owner(self.course, self.peer)

    def test_teacher_with_different_subject_cannot_access_shared_course(self):
        with self.assertRaisesMessage(Exception, "您没有权限操作此课程"):
            _check_course_owner(self.course, self.other_subject)
