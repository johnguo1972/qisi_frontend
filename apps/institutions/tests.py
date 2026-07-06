from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.institutions.models import (
    Institution,
    Class,
    _generate_invite_code,
    InstitutionMember,
    ClassJoinRequest,
    ClassStudent,
)


class InstitutionModelTest(TestCase):
    """Tests for the Institution model."""

    def test_str_representation(self):
        inst = Institution.objects.create(institution_name='Test School')
        self.assertEqual(str(inst), 'Test School')

    def test_default_status(self):
        inst = Institution.objects.create(institution_name='Test School')
        self.assertEqual(inst.status, 'active')

    def test_create_institution_with_all_fields(self):
        inst = Institution.objects.create(
            institution_name='Full School',
            contact_name='John Doe',
            contact_phone='13800138000',
            contact_email='john@example.com',
            address='123 Test St',
        )
        self.assertEqual(inst.institution_name, 'Full School')
        self.assertEqual(inst.contact_name, 'John Doe')
        self.assertEqual(inst.contact_phone, '13800138000')
        self.assertEqual(inst.contact_email, 'john@example.com')
        self.assertEqual(inst.address, '123 Test St')


class ClassModelTest(TestCase):
    """Tests for the Class model."""

    def setUp(self):
        self.institution = Institution.objects.create(
            institution_name='Test School',
        )

    def test_auto_generated_class_no(self):
        cls = Class.objects.create(
            institution=self.institution,
            class_name='Math 101',
        )
        self.assertTrue(cls.class_no.startswith('CLS-'))
        self.assertEqual(len(cls.class_no.split('-')[1]), 8)

    def test_auto_generated_invite_code(self):
        cls = Class.objects.create(
            institution=self.institution,
            class_name='Math 101',
        )
        self.assertEqual(len(cls.invite_code), 8)
        self.assertTrue(cls.invite_code.isalnum())
        self.assertTrue(cls.invite_code.isupper())

    def test_invite_code_uniqueness(self):
        """Generate 100 classes and verify all invite codes are unique."""
        codes = []
        for i in range(100):
            cls = Class(
                institution=self.institution,
                class_name=f'Class {i}',
            )
            cls.save()
            codes.append(cls.invite_code)
        self.assertEqual(len(codes), len(set(codes)), 'Duplicate invite codes found')

    def test_default_values(self):
        cls = Class.objects.create(
            institution=self.institution,
            class_name='Science 201',
        )
        self.assertEqual(cls.max_students, 50)
        self.assertTrue(cls.allow_invite_join)
        self.assertEqual(cls.status, 'active')

    def test_str_representation(self):
        cls = Class.objects.create(
            institution=self.institution,
            class_name='English 301',
        )
        self.assertEqual(str(cls), 'English 301')


class InviteCodeFunctionTest(TestCase):
    """Tests for the _generate_invite_code utility function."""

    def test_length_is_8(self):
        code = _generate_invite_code()
        self.assertEqual(len(code), 8)

    def test_uppercase_alphanumeric(self):
        code = _generate_invite_code()
        self.assertTrue(code.isalnum())
        self.assertTrue(code.isupper())

    def test_randomness(self):
        codes = [_generate_invite_code() for _ in range(1000)]
        # At least 99% unique (statistical guarantee)
        unique_count = len(set(codes))
        self.assertGreaterEqual(unique_count, 990)


# ──────────────────────────────────────────────
# API Tests
# ──────────────────────────────────────────────


class InstitutionAPITest(TestCase):
    """Tests for Institution CRUD API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = UserAccount.objects.create(
            mobile='13800000001',
            display_name='Platform Admin',
            role_type='admin',
        )
        self.teacher_user = UserAccount.objects.create(
            mobile='13800000002',
            display_name='Regular Teacher',
            role_type='teacher',
        )

    def test_create_institution(self):
        """Admin can create institutions via POST /api/v1/admin/institutions."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            '/api/v1/admin/institutions',
            {'institution_name': 'Test Primary School'},
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['code'], 0)
        self.assertEqual(data['data']['institution_name'], 'Test Primary School')
        # Verify institution was created in DB
        self.assertTrue(
            Institution.objects.filter(institution_name='Test Primary School').exists()
        )

    def test_list_institutions(self):
        """GET /api/v1/admin/institutions returns paginated list."""
        Institution.objects.create(institution_name='School A')
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get('/api/v1/admin/institutions')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 0)
        self.assertEqual(data['data']['total'], 1)
        self.assertEqual(data['data']['items'][0]['institution_name'], 'School A')

    def test_non_admin_cannot_create(self):
        """Non-admin users get 403 when trying to create institutions."""
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            '/api/v1/admin/institutions',
            {'institution_name': 'Unauthorized School'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)


class ClassAPITest(TestCase):
    """Tests for Class CRUD API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = UserAccount.objects.create(
            mobile='13800000010',
            display_name='Admin User',
            role_type='admin',
        )
        self.teacher_user = UserAccount.objects.create(
            mobile='13800000011',
            display_name='Teacher User',
            role_type='teacher',
        )
        self.student_user = UserAccount.objects.create(
            mobile='13800000012',
            display_name='Student User',
            role_type='student',
        )
        self.institution = Institution.objects.create(
            institution_name='Test School',
        )
        # Add teacher as an active member of the institution
        InstitutionMember.objects.create(
            institution=self.institution,
            user=self.teacher_user,
            role='teacher',
            status='active',
        )

    def test_create_class(self):
        """Teacher can create a class via POST /api/v1/classes."""
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            '/api/v1/classes',
            {
                'institution_id': self.institution.id,
                'class_name': 'Math 101',
                'description': 'Intro to math',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['code'], 0)
        self.assertEqual(data['data']['class_name'], 'Math 101')
        self.assertEqual(len(data['data']['invite_code']), 8)
        # Verify class was created in DB
        cls = Class.objects.get(class_name='Math 101')
        self.assertEqual(cls.institution_id, self.institution.id)
        self.assertEqual(len(cls.invite_code), 8)

    def test_list_classes(self):
        """GET /api/v1/classes lists classes where user is a teacher."""
        cls = Class.objects.create(
            institution=self.institution,
            class_name='Science 201',
            creator_teacher=self.teacher_user,
        )
        # Create ClassTeacher relation
        from apps.institutions.models import ClassTeacher
        ClassTeacher.objects.create(
            class_obj=cls, teacher=self.teacher_user, role='owner',
        )
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get('/api/v1/classes')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 0)
        self.assertEqual(data['data']['total'], 1)
        self.assertEqual(len(data['data']['items']), 1)
        self.assertEqual(data['data']['items'][0]['class_name'], 'Science 201')

    def test_non_member_cannot_create(self):
        """Students who are not institution members get 403 when creating a class."""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            '/api/v1/classes',
            {
                'institution_id': self.institution.id,
                'class_name': 'Unauthorized Class',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 403)


class JoinRequestAPITest(TestCase):
    """Tests for join request and invite code join API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.teacher_user = UserAccount.objects.create(
            mobile='13800000020',
            display_name='Teacher User',
            role_type='teacher',
        )
        self.student_user = UserAccount.objects.create(
            mobile='13800000021',
            display_name='Student User',
            role_type='student',
        )
        self.institution = Institution.objects.create(
            institution_name='Test School',
        )
        InstitutionMember.objects.create(
            institution=self.institution,
            user=self.teacher_user,
            role='teacher',
            status='active',
        )
        self.class_obj = Class.objects.create(
            institution=self.institution,
            class_name='English 301',
            creator_teacher=self.teacher_user,
            allow_invite_join=True,
        )
        from apps.institutions.models import ClassTeacher
        ClassTeacher.objects.create(
            class_obj=self.class_obj, teacher=self.teacher_user, role='owner',
        )

    def test_student_submit_join_request(self):
        """Student can submit a join request via POST /api/v1/classes/join-request."""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            '/api/v1/classes/join-request',
            {
                'class_id': self.class_obj.id,
                'applicant_name': self.student_user.display_name,
                'applicant_phone': self.student_user.mobile,
                'request_type': 'self_apply',
                'message': 'Please approve',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['code'], 0)
        self.assertEqual(data['data']['status'], 'pending')
        # Verify join request was created in DB
        self.assertTrue(
            ClassJoinRequest.objects.filter(
                class_obj=self.class_obj,
                applicant=self.student_user,
                status='pending',
            ).exists()
        )

    def test_teacher_approve_request(self):
        """Teacher can approve a join request via POST /api/v1/classes/join-requests/<id>/approve."""
        join_req = ClassJoinRequest.objects.create(
            class_obj=self.class_obj,
            applicant=self.student_user,
            applicant_name=self.student_user.display_name,
            applicant_phone=self.student_user.mobile,
            request_type='self_apply',
            status='pending',
        )
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.post(
            f'/api/v1/classes/join-requests/{join_req.id}/approve',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 0)
        # Verify request status updated
        join_req.refresh_from_db()
        self.assertEqual(join_req.status, 'approved')
        # Verify ClassStudent is active
        self.assertTrue(
            ClassStudent.objects.filter(
                class_obj=self.class_obj,
                student=self.student_user,
                status='active',
            ).exists()
        )

    def test_join_by_invite_code(self):
        """Student can join a class by invite code via POST /api/v1/student/classes/join-by-code."""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            '/api/v1/student/classes/join-by-code',
            {
                'invite_code': self.class_obj.invite_code,
                'applicant_name': self.student_user.display_name,
                'applicant_phone': self.student_user.mobile,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['code'], 0)
        self.assertEqual(data['data']['class_id'], self.class_obj.id)
        # Verify ClassStudent with join_type='invite'
        self.assertTrue(
            ClassStudent.objects.filter(
                class_obj=self.class_obj,
                student=self.student_user,
                join_type='invite',
                status='active',
            ).exists()
        )

    def test_invalid_invite_code(self):
        """Student gets 400 when using an invalid invite code."""
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            '/api/v1/student/classes/join-by-code',
            {
                'invite_code': 'INVALID0',
                'applicant_name': self.student_user.display_name,
                'applicant_phone': self.student_user.mobile,
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('invite_code', str(data))


class EndToEndFlowTest(TestCase):
    """Complete flow: admin→institution→teacher→class→student join→verify."""

    def setUp(self):
        from apps.institutions.models import ClassTeacher
        self.ClassTeacher = ClassTeacher
        self.client = APIClient()
        self.admin = UserAccount.objects.create(
            role_type='admin', mobile='13800000001', display_name='Admin',
        )
        self.teacher = UserAccount.objects.create(
            role_type='teacher', mobile='13800000002', display_name='Teacher Li',
        )
        self.student = UserAccount.objects.create(
            role_type='student', mobile='13800000003', display_name='Student Wang',
        )

    def test_full_flow(self):
        # 1. Admin creates institution
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post('/api/v1/admin/institutions', {
            'institution_name': 'Test Academy',
            'contact_name': 'John',
            'contact_phone': '13800000000',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        inst_id = resp.data['data']['id']

        # 2. Admin adds teacher to institution
        resp = self.client.post(f'/api/v1/institutions/{inst_id}/members', {
            'mobile': '13800000002',
            'display_name': 'Teacher Li',
            'role': 'teacher',
        }, format='json')
        self.assertEqual(resp.status_code, 201)

        # 3. Teacher creates class
        self.client.force_authenticate(user=self.teacher)
        resp = self.client.post('/api/v1/classes', {
            'institution_id': inst_id,
            'class_name': 'Math 101',
            'description': 'Basic math',
            'allow_invite_join': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        cls_id = resp.data['data']['id']
        invite_code = resp.data['data']['invite_code']

        # 4. Student joins by invite code
        self.client.force_authenticate(user=self.student)
        resp = self.client.post('/api/v1/student/classes/join-by-code', {
            'invite_code': invite_code,
            'applicant_name': self.student.display_name,
            'applicant_phone': self.student.mobile,
        }, format='json')
        self.assertEqual(resp.status_code, 201)

        # 5. Verify student is in class
        resp = self.client.get('/api/v1/student/my-classes')
        self.assertEqual(resp.status_code, 200)
        items = resp.data['data']['items']
        # Filter to only our created class
        our_class = [i for i in items if i['class_name'] == 'Math 101']
        self.assertEqual(len(our_class), 1)
        self.assertEqual(our_class[0]['class_name'], 'Math 101')

        # 6. Teacher sees student in class
        self.client.force_authenticate(user=self.teacher)
        resp = self.client.get(f'/api/v1/classes/{cls_id}/students')
        self.assertEqual(resp.status_code, 200)
        items = resp.data['data']['items']
        student_names = [s.get('student_name') for s in items]
        self.assertIn('Student Wang', student_names)
