from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import StudentParentBind, UserAccount
from apps.accounts.roles import grant_user_role, has_user_role
from apps.accounts.services import generate_tokens
from apps.institutions.models import Class, ClassStudent, ClassTeacher, Institution


class TeacherStudentManagementAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.teacher = UserAccount.objects.create(
            mobile='13810000001', display_name='教师', role_type='teacher',
        )
        grant_user_role(self.teacher, 'teacher')
        self.institution = Institution.objects.create(institution_name='测试学校')
        self.class_obj = Class.objects.create(
            institution=self.institution,
            creator_teacher=self.teacher,
            class_name='高一一班',
            grade_level='高一',
        )
        ClassTeacher.objects.create(
            class_obj=self.class_obj, teacher=self.teacher, role='owner',
        )
        token = generate_tokens(self.teacher, 'teacher')['access_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        self.url = f'/api/v1/classes/{self.class_obj.id}/students'

    def add_payload(self, **overrides):
        payload = {
            'student_name': '张三',
            'school': '测试中学',
            'grade_level': '高一',
            'target_class_id': str(self.class_obj.id),
            'class_type': 'A_PLUS',
            'student_mobile': '13810000002',
            'parent_name': '张三家长',
            'parent_mobile': '13810000003',
        }
        payload.update(overrides)
        return payload

    def test_add_student_creates_account_roles_binding_and_list_data(self):
        response = self.client.post(self.url, self.add_payload(), format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['code'], 0)
        student = UserAccount.objects.get(mobile='13810000002')
        parent = UserAccount.objects.get(mobile='13810000003')
        membership = ClassStudent.objects.get(
            class_obj=self.class_obj, student=student,
        )
        binding = StudentParentBind.objects.get(
            student_user_id=student, parent_user_id=parent,
        )

        self.assertEqual(student.display_name, '张三')
        self.assertEqual(student.school, '测试中学')
        self.assertEqual(student.grade_level, '高一')
        self.assertTrue(has_user_role(student, 'student'))
        self.assertTrue(has_user_role(parent, 'parent'))
        self.assertEqual(membership.grade_level, '高一')
        self.assertEqual(membership.class_type, 'A_PLUS')
        self.assertEqual(membership.join_type, 'manual')
        self.assertEqual(binding.bind_status, 'active')
        self.assertTrue(binding.is_primary)

        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, 200)
        item = list_response.json()['data']['items'][0]
        self.assertEqual(item['student_name'], '张三')
        self.assertEqual(item['school'], '测试中学')
        self.assertEqual(item['grade_level'], '高一')
        self.assertEqual(item['class_name'], '高一一班')
        self.assertEqual(item['class_type'], 'A_PLUS')
        self.assertEqual(item['parent_name'], '张三家长')
        self.assertEqual(item['parent_mobile'], '13810000003')

    def test_patch_updates_student_fields_and_replaces_primary_parent(self):
        self.client.post(self.url, self.add_payload(), format='json')
        student = UserAccount.objects.get(mobile='13810000002')
        update_url = f'/api/v1/classes/{self.class_obj.id}/students/{student.id}'

        response = self.client.patch(update_url, self.add_payload(
            student_name='李四',
            school='新测试学校',
            class_type='S',
            student_mobile='13810000004',
            parent_name='李四家长',
            parent_mobile='13810000005',
        ), format='json')

        self.assertEqual(response.status_code, 200)
        student.refresh_from_db()
        membership = ClassStudent.objects.get(
            class_obj=self.class_obj, student=student,
        )
        old_binding = StudentParentBind.objects.get(
            student_user_id=student, parent_user_id__mobile='13810000003',
        )
        new_binding = StudentParentBind.objects.get(
            student_user_id=student, parent_user_id__mobile='13810000005',
        )
        self.assertEqual(student.mobile, '13810000004')
        self.assertEqual(student.display_name, '李四')
        self.assertEqual(student.school, '新测试学校')
        self.assertEqual(membership.class_type, 'S')
        self.assertEqual(old_binding.bind_status, 'active')
        self.assertFalse(old_binding.is_primary)
        self.assertEqual(new_binding.bind_status, 'active')
        self.assertTrue(new_binding.is_primary)
        self.assertTrue(has_user_role(UserAccount.objects.get(mobile='13810000005'), 'parent'))

    def test_parent_name_and_mobile_must_be_paired(self):
        response = self.client.post(
            self.url,
            self.add_payload(parent_name='仅有姓名', parent_mobile=''),
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(UserAccount.objects.filter(mobile='13810000002').count(), 0)

    def test_grade_must_match_target_class(self):
        response = self.client.post(
            self.url,
            self.add_payload(grade_level='高二'),
            format='json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['code'], 'GRADE_CLASS_MISMATCH')
        self.assertEqual(UserAccount.objects.filter(mobile='13810000002').count(), 0)
