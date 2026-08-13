from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role, has_user_role
from apps.institutions.models import (
    Institution,
    Class,
    _generate_invite_code,
    InstitutionMember,
    ClassJoinRequest,
    ClassStudent,
)


class InstitutionMemberMultiRoleAPITest(TestCase):
    """Institution roles are independent relationships, aggregated per user."""

    def setUp(self):
        self.client = APIClient()
        self.platform_admin = UserAccount.objects.create(
            mobile='13800000101',
            display_name='Platform Admin',
            role_type='admin',
        )
        grant_user_role(self.platform_admin, 'admin')
        self.member_user = UserAccount.objects.create(
            mobile='13800000102',
            display_name='Multi Role Member',
            role_type='student',
        )
        self.institution = Institution.objects.create(
            institution_name='Multi Role School',
        )
        self.members_url = f'/api/v1/institutions/{self.institution.id}/members'
        self.client.force_authenticate(user=self.platform_admin)

    def test_active_institution_admin_can_also_be_added_as_teacher(self):
        InstitutionMember.objects.create(
            institution=self.institution,
            user=self.platform_admin,
            role='admin',
            status='active',
        )

        response = self.client.post(self.members_url, {
            'mobile': self.platform_admin.mobile,
            'display_name': self.platform_admin.display_name,
            'role': 'teacher',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(InstitutionMember.objects.filter(
                institution=self.institution,
                user=self.platform_admin,
                status='active',
            ).values_list('role', flat=True).order_by('role')),
            ['admin', 'teacher'],
        )
        self.assertTrue(has_user_role(self.platform_admin, 'admin'))
        self.assertTrue(has_user_role(self.platform_admin, 'teacher'))

    def test_member_list_aggregates_roles_in_fixed_order(self):
        InstitutionMember.objects.create(
            institution=self.institution,
            user=self.member_user,
            role='teacher',
            status='active',
        )
        InstitutionMember.objects.create(
            institution=self.institution,
            user=self.member_user,
            role='admin',
            status='active',
        )

        response = self.client.get(self.members_url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()['data']
        self.assertEqual(payload['total'], 1)
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(payload['items'][0]['user_id'], str(self.member_user.id))
        self.assertEqual(payload['items'][0]['roles'], ['admin', 'teacher'])

    def test_duplicate_teacher_add_is_idempotent_and_preserves_legacy_role(self):
        InstitutionMember.objects.create(
            institution=self.institution,
            user=self.member_user,
            role='teacher',
            status='active',
        )

        for _ in range(2):
            response = self.client.post(self.members_url, {
                'mobile': self.member_user.mobile,
                'display_name': self.member_user.display_name,
                'role': 'teacher',
            }, format='json')
            self.assertEqual(response.status_code, 200)

        self.assertEqual(InstitutionMember.objects.filter(
            institution=self.institution,
            user=self.member_user,
            role='teacher',
        ).count(), 1)
        self.assertTrue(has_user_role(self.member_user, 'teacher'))
        self.member_user.refresh_from_db()
        self.assertEqual(self.member_user.role_type, 'student')

    def test_add_restores_inactive_role(self):
        member = InstitutionMember.objects.create(
            institution=self.institution,
            user=self.member_user,
            role='teacher',
            status='removed',
        )

        response = self.client.post(self.members_url, {
            'mobile': self.member_user.mobile,
            'display_name': self.member_user.display_name,
            'role': 'teacher',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        member.refresh_from_db()
        self.assertEqual(member.status, 'active')
        self.assertTrue(has_user_role(self.member_user, 'teacher'))

    def test_adding_institution_admin_does_not_grant_global_admin(self):
        response = self.client.post(self.members_url, {
            'mobile': self.member_user.mobile,
            'display_name': self.member_user.display_name,
            'role': 'admin',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(InstitutionMember.objects.filter(
            institution=self.institution,
            user=self.member_user,
            role='admin',
            status='active',
        ).exists())
        self.assertFalse(has_user_role(self.member_user, 'admin'))
        self.member_user.refresh_from_db()
        self.assertEqual(self.member_user.role_type, 'student')

    def test_update_roles_applies_set_diff_and_grants_teacher(self):
        admin_member = InstitutionMember.objects.create(
            institution=self.institution,
            user=self.member_user,
            role='admin',
            status='active',
        )
        teacher_member = InstitutionMember.objects.create(
            institution=self.institution,
            user=self.member_user,
            role='teacher',
            status='removed',
        )

        response = self.client.put(
            f'{self.members_url}/{self.member_user.id}',
            {'roles': ['teacher']},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        admin_member.refresh_from_db()
        teacher_member.refresh_from_db()
        self.assertEqual(admin_member.status, 'removed')
        self.assertEqual(teacher_member.status, 'active')
        self.assertTrue(has_user_role(self.member_user, 'teacher'))

    def test_remove_member_deactivates_all_institution_roles(self):
        for role in ('admin', 'teacher'):
            InstitutionMember.objects.create(
                institution=self.institution,
                user=self.member_user,
                role=role,
                status='active',
            )

        response = self.client.put(
            f'{self.members_url}/{self.member_user.id}',
            {'status': 'removed'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(InstitutionMember.objects.filter(
            institution=self.institution,
            user=self.member_user,
            status='active',
        ).exists())
        self.assertEqual(InstitutionMember.objects.filter(
            institution=self.institution,
            user=self.member_user,
            status='removed',
        ).count(), 2)


class InstitutionMultiRoleMigrationTest(TransactionTestCase):
    migrate_from = [
        ('accounts', '0003_userrole'),
        ('institutions', '0001_initial'),
    ]
    migrate_to = [
        ('accounts', '0003_userrole'),
        ('institutions', '0002_multi_role_memberships'),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        UserAccount = old_apps.get_model('accounts', 'UserAccount')
        UserRole = old_apps.get_model('accounts', 'UserRole')
        Institution = old_apps.get_model('institutions', 'Institution')
        InstitutionMember = old_apps.get_model('institutions', 'InstitutionMember')
        Class = old_apps.get_model('institutions', 'Class')
        ClassStudent = old_apps.get_model('institutions', 'ClassStudent')

        self.teacher_id = UserAccount.objects.create(
            mobile='13800000111', display_name='Teacher', role_type='student',
        ).id
        self.student_id = UserAccount.objects.create(
            mobile='13800000112', display_name='Student', role_type='parent',
        ).id
        self.institution_admin_id = UserAccount.objects.create(
            mobile='13800000113', display_name='Institution Admin', role_type='student',
        ).id
        self.inactive_teacher_id = UserAccount.objects.create(
            mobile='13800000114', display_name='Inactive Teacher', role_type='student',
        ).id
        self.inactive_student_id = UserAccount.objects.create(
            mobile='13800000115', display_name='Inactive Student', role_type='parent',
        ).id
        institution = Institution.objects.create(institution_name='Migration School')
        InstitutionMember.objects.create(
            institution_id=institution.id,
            user_id=self.teacher_id,
            role='teacher',
            status='active',
        )
        InstitutionMember.objects.create(
            institution_id=institution.id,
            user_id=self.institution_admin_id,
            role='admin',
            status='active',
        )
        InstitutionMember.objects.create(
            institution_id=institution.id,
            user_id=self.inactive_teacher_id,
            role='teacher',
            status='removed',
        )
        class_obj = Class.objects.create(
            institution_id=institution.id,
            class_no='CLS-MIGRATE',
            class_name='Migration Class',
            invite_code='MIGRATE1',
        )
        ClassStudent.objects.create(
            class_obj_id=class_obj.id,
            student_id=self.student_id,
            join_type='manual',
            status='active',
        )
        ClassStudent.objects.create(
            class_obj_id=class_obj.id,
            student_id=self.inactive_student_id,
            join_type='manual',
            status='removed',
        )
        UserRole.objects.update_or_create(
            user_id=self.teacher_id,
            role='teacher',
            defaults={'status': 'inactive'},
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
        super().tearDown()

    def test_imports_active_relationship_roles_without_admin_escalation(self):
        UserRole = self.apps.get_model('accounts', 'UserRole')
        self.assertTrue(UserRole.objects.filter(
            user_id=self.teacher_id, role='teacher', status='active',
        ).exists())
        self.assertTrue(UserRole.objects.filter(
            user_id=self.student_id, role='student', status='active',
        ).exists())
        self.assertFalse(UserRole.objects.filter(
            user_id=self.institution_admin_id, role='admin', status='active',
        ).exists())
        self.assertFalse(UserRole.objects.filter(
            user_id=self.inactive_teacher_id, role='teacher', status='active',
        ).exists())
        self.assertFalse(UserRole.objects.filter(
            user_id=self.inactive_student_id, role='student', status='active',
        ).exists())


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
        self.assertEqual(data['data']['class_id'], str(self.class_obj.id))
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
        self.assertEqual(resp.status_code, 200)

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
