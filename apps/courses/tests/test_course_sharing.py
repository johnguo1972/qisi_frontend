from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.courses.models import Course, CourseCollaborator
from apps.institutions.models import Institution, InstitutionMember
from apps.courses.views import _check_course_owner, course_list_or_create


class CourseSharingTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(institution_name="共享测试机构")
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
            institution=self.institution,
        )
        for teacher in [self.owner, self.peer, self.other_subject]:
            InstitutionMember.objects.create(
                institution=self.institution, user=teacher, role='teacher', status='active',
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

    def test_creator_can_list_and_edit_own_course_without_profile_scope(self):
        self.owner.subject = None
        self.owner.stages = None
        self.owner.save(update_fields=["subject", "stages"])
        request = APIRequestFactory().get("/api/v1/courses/")
        force_authenticate(request, user=self.owner)

        response = course_list_or_create(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["data"]], [str(self.course.id)])
        _check_course_owner(self.course, self.owner)

    def test_teacher_with_different_subject_cannot_access_shared_course(self):
        with self.assertRaisesMessage(Exception, "您没有权限操作此课程"):
            _check_course_owner(self.course, self.other_subject)

    def test_chinese_subject_input_is_normalized_to_english_code(self):
        course = Course.objects.create(
            name='中文输入兼容课程',
            subject='物理',
            grade_level='九年级',
            teacher=self.owner,
            institution=self.institution,
        )
        self.assertEqual(course.subject, 'physics')

    def test_same_institution_subject_and_stage_can_share(self):
        request = APIRequestFactory().get('/api/v1/courses/')
        force_authenticate(request, user=self.peer)
        response = course_list_or_create(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(str(self.course.id), [item['id'] for item in response.data['data']])

    def test_other_institution_cannot_see_course(self):
        other_institution = Institution.objects.create(institution_name='隔离机构')
        outsider = UserAccount.objects.create(
            mobile='13900001005', display_name='隔离教师', role_type='teacher',
            subject='physics', stages=['初中'],
        )
        InstitutionMember.objects.create(
            institution=other_institution, user=outsider, role='teacher', status='active',
        )
        request = APIRequestFactory().get('/api/v1/courses/')
        force_authenticate(request, user=outsider)
        response = course_list_or_create(request)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.course.id), [item['id'] for item in response.data['data']])

    def test_explicit_viewer_can_read_but_not_edit(self):
        viewer = UserAccount.objects.create(
            mobile='13900001006', display_name='只读教师', role_type='teacher',
            subject='math', stages=['高中'],
        )
        InstitutionMember.objects.create(
            institution=self.institution, user=viewer, role='teacher', status='active',
        )
        CourseCollaborator.objects.create(course=self.course, user=viewer, role='viewer')
        request = APIRequestFactory().get('/api/v1/courses/')
        force_authenticate(request, user=viewer)
        response = course_list_or_create(request)
        self.assertIn(str(self.course.id), [item['id'] for item in response.data['data']])
        with self.assertRaisesMessage(Exception, '您没有权限操作此课程'):
            _check_course_owner(self.course, viewer)
