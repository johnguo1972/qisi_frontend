from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount
from apps.courses.models import Course
from apps.courses.views import course_list_or_create
from apps.institutions.models import Class, ClassTeacher, Institution, InstitutionMember


class CourseGradeValidationTests(TestCase):
    def setUp(self):
        self.institution = Institution.objects.create(institution_name='grade validation school')
        self.teacher = UserAccount.objects.create(
            mobile='13900002001', display_name='course teacher', role_type='teacher',
        )
        InstitutionMember.objects.create(
            institution=self.institution, user=self.teacher, role='teacher', status='active',
        )
        self.class_obj = Class.objects.create(
            institution=self.institution,
            creator_teacher=self.teacher,
            class_name='weekend intensive class',
        )
        ClassTeacher.objects.create(class_obj=self.class_obj, teacher=self.teacher, role='owner')

    def post_create(self, **data):
        request = APIRequestFactory().post('/api/v1/courses/', data, format='json')
        force_authenticate(request, user=self.teacher)
        return course_list_or_create(request)

    def test_unconfigured_class_accepts_grade_selected_in_create_form(self):
        response = self.post_create(
            name='manual grade lesson', subject='physics', grade_level='八年级',
            institution_id=str(self.institution.id), class_id=str(self.class_obj.id),
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Course.objects.get(name='manual grade lesson').grade_level, '八年级')

    def test_unconfigured_class_without_grade_has_actionable_error(self):
        response = self.post_create(
            name='missing grade lesson', subject='physics',
            institution_id=str(self.institution.id), class_id=str(self.class_obj.id),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('grade_level', response.data)
