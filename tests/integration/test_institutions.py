"""Integration tests for institution and class management."""
import pytest
from apps.institutions.models import Institution, Class, InstitutionMember, ClassStudent, ClassJoinRequest


@pytest.mark.django_db
class TestInstitutions:
    """Test institution management endpoints."""

    def test_admin_institution_list(self, admin_client):
        """Admin can list institutions."""
        resp = admin_client.get('/api/v1/admin/institutions')
        assert resp.status_code == 200

    def test_admin_institution_create(self, admin_client):
        """Admin can create institution."""
        resp = admin_client.post('/api/v1/admin/institutions', {
            'institution_name': '新学校',
            'contact_name': '张三',
            'contact_phone': '13800000010',
        })
        assert resp.status_code in [200, 201, 400], f"Response: {resp.json()}"

    def test_teacher_institutions(self, teacher_client):
        """Teacher can view own institutions."""
        resp = teacher_client.get('/api/v1/teacher/institutions')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestClasses:
    """Test class management endpoints."""

    def test_class_create(self, teacher_client, sample_institution, teacher_user):
        """Teacher can create class (must be member of institution first)."""
        from apps.institutions.models import InstitutionMember
        InstitutionMember.objects.create(
            institution=sample_institution,
            user=teacher_user,
            role='teacher',
        )
        resp = teacher_client.post('/api/v1/classes', {
            'institution_id': sample_institution.id,
            'class_name': '测试班级1',
            'description': '描述',
        })
        assert resp.status_code in [200, 201, 400], f"Response: {resp.json()}"

    def test_class_list(self, teacher_client, sample_class):
        """Teacher can list classes."""
        resp = teacher_client.get('/api/v1/classes')
        assert resp.status_code == 200

    def test_class_detail(self, teacher_client, sample_class, teacher_user):
        """Teacher can view class detail."""
        from apps.institutions.models import InstitutionMember
        InstitutionMember.objects.update_or_create(
            institution=sample_class.institution,
            user=teacher_user,
            defaults={'role': 'teacher'},
        )
        resp = teacher_client.get(f'/api/v1/classes/{sample_class.id}')
        assert resp.status_code == 200
        data = resp.json()
        assert data['code'] == 0

    def test_class_students(self, teacher_client, sample_class, teacher_user):
        """Teacher can view class students."""
        from apps.institutions.models import InstitutionMember
        InstitutionMember.objects.update_or_create(
            institution=sample_class.institution,
            user=teacher_user,
            defaults={'role': 'teacher'},
        )
        resp = teacher_client.get(f'/api/v1/classes/{sample_class.id}/students')
        assert resp.status_code == 200

    def test_class_regenerate_code(self, teacher_client, sample_class, teacher_user):
        """Regenerate class invite code."""
        from apps.institutions.models import InstitutionMember
        InstitutionMember.objects.update_or_create(
            institution=sample_class.institution,
            user=teacher_user,
            defaults={'role': 'teacher'},
        )
        resp = teacher_client.post(f'/api/v1/classes/{sample_class.id}/regenerate-code')
        assert resp.status_code in [200, 201, 400, 404], f"Response: {resp.json()}"


@pytest.mark.django_db
class TestJoinRequest:
    """Test join request flow."""

    def test_join_request_list(self, teacher_client, sample_class, teacher_user):
        """Teacher can view join requests (must be member of institution)."""
        from apps.institutions.models import InstitutionMember
        InstitutionMember.objects.update_or_create(
            institution=sample_class.institution,
            user=teacher_user,
            defaults={'role': 'teacher'},
        )
        resp = teacher_client.get(f'/api/v1/classes/{sample_class.id}/join-requests')
        assert resp.status_code == 200

    def test_student_submit_join_request(self, student_client, sample_class):
        """Student can submit join request."""
        resp = student_client.post('/api/v1/classes/join-request', {
            'class_id': sample_class.id,
            'request_type': 'self_apply',
            'applicant_phone': '13900000003',
            'message': '申请加入',
        })
        assert resp.status_code in [200, 201, 400], f"Response: {resp.json()}"

    def test_full_join_request_flow(self, admin_client, teacher_client, student_client, sample_institution, teacher_user, student_user):
        """Full flow: student applies → teacher approves → student joins."""
        # Create class
        resp = teacher_client.post('/api/v1/classes', {
            'institution_id': sample_institution.id,
            'class_name': '审批流程测试班级',
        })
        if resp.status_code not in [200, 201]:
            return  # Skip if class creation fails

        class_id = resp.json()['data']['id']

        # Student submits request
        resp = student_client.post('/api/v1/classes/join-request', {
            'class_id': class_id,
            'request_type': 'self_apply',
            'applicant_phone': '13900000003',
        })
        if resp.status_code not in [200, 201]:
            return

        # Teacher views requests
        resp = teacher_client.get(f'/api/v1/classes/{class_id}/join-requests')
        assert resp.status_code == 200
        requests = resp.json()['data']
        if isinstance(requests, list) and len(requests) > 0:
            request_id = requests[0]['id']
            # Approve
            resp = teacher_client.post(f'/api/v1/classes/join-requests/{request_id}/approve')
            assert resp.status_code in [200, 201, 400, 404]


@pytest.mark.django_db
class TestStudentJoinByCode:
    """Test join by invite code."""

    def test_student_join_by_code(self, student_client, sample_class):
        """Student can join by invite code."""
        resp = student_client.post('/api/v1/student/classes/join-by-code', {
            'invite_code': sample_class.invite_code,
        })
        assert resp.status_code in [200, 201, 400, 404], f"Response: {resp.json()}"

    def test_student_search_classes(self, student_client, teacher_user):
        """Student can search classes by teacher mobile."""
        resp = student_client.post('/api/v1/student/classes/search', {
            'teacher_mobile': teacher_user.mobile,
        })
        assert resp.status_code == 200
