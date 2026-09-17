from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.courses.models import Course, CourseClass, CourseCollaborator
from apps.institutions.models import Class, ClassTeacher, Institution, InstitutionMember
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

    def test_teacher_can_filter_courses_by_managed_class(self):
        selected_class = Class.objects.create(
            institution=self.institution,
            creator_teacher=self.owner,
            class_name='筛选班级',
        )
        other_class = Class.objects.create(
            institution=self.institution,
            creator_teacher=self.owner,
            class_name='其他班级',
        )
        ClassTeacher.objects.create(class_obj=selected_class, teacher=self.owner, role='owner')
        ClassTeacher.objects.create(class_obj=other_class, teacher=self.owner, role='owner')
        CourseClass.objects.create(course=self.course, class_obj=selected_class)

        request = APIRequestFactory().get(f'/api/v1/courses/?class_id={selected_class.id}')
        force_authenticate(request, user=self.owner)

        response = course_list_or_create(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data['data']], [str(self.course.id)])

    def test_create_course_with_class_id_creates_active_class_relation(self):
        selected_class = Class.objects.create(
            institution=self.institution,
            creator_teacher=self.owner,
            class_name='新建课次班级',
        )
        ClassTeacher.objects.create(class_obj=selected_class, teacher=self.owner, role='owner')
        request = APIRequestFactory().post(
            '/api/v1/courses/',
            {
                'name': '新建课次测试',
                'subject': 'physics',
                'grade_level': '八年级',
                'institution_id': str(self.institution.id),
                'class_id': str(selected_class.id),
            },
            format='json',
        )
        force_authenticate(request, user=self.owner)

        response = course_list_or_create(request)

        self.assertEqual(response.status_code, 201)
        created_course = Course.objects.get(name='新建课次测试')
        self.assertTrue(
            CourseClass.objects.filter(
                course=created_course,
                class_obj=selected_class,
                status='active',
            ).exists()
        )

    def test_create_course_uses_class_name_grade_when_grade_form_is_hidden(self):
        selected_class = Class.objects.create(
            institution=self.institution,
            creator_teacher=self.owner,
            class_name='八年级8班',
        )
        ClassTeacher.objects.create(class_obj=selected_class, teacher=self.owner, role='owner')
        request = APIRequestFactory().post(
            '/api/v1/courses/',
            {
                'name': '隐藏年级表单创建测试',
                'subject': 'physics',
                'institution_id': str(self.institution.id),
                'class_id': str(selected_class.id),
            },
            format='json',
        )
        force_authenticate(request, user=self.owner)

        response = course_list_or_create(request)

        self.assertEqual(response.status_code, 201)
        created_course = Course.objects.get(name='隐藏年级表单创建测试')
        self.assertEqual(created_course.grade_level, '八年级')
