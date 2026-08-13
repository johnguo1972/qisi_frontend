import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StudentParentBind, UserAccount
from apps.accounts.roles import grant_user_role, has_user_role
from apps.accounts.services import generate_tokens
from apps.institutions.models import (
    Class,
    ClassJoinRequest,
    ClassStudent,
    ClassTeacher,
    Institution,
    InstitutionMember,
)
from apps.missions.models import LearningMission
from apps.missions.views import _mission_student_ids
from apps.qrcode.views import _mission_students


pytestmark = pytest.mark.django_db


def make_user(mobile, legacy_role):
    return UserAccount.objects.create(
        mobile=mobile,
        login_name=mobile,
        display_name=mobile,
        role_type=legacy_role,
    )


def client_for(user, active_role):
    token = generate_tokens(user, active_role)["access_token"]
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def make_institution(name="Role School"):
    return Institution.objects.create(institution_name=name)


def make_class(institution, teacher, name="Role Class"):
    return Class.objects.create(
        institution=institution,
        class_name=name,
        creator_teacher=teacher,
        allow_invite_join=True,
    )


def test_admin_session_cannot_create_class_from_teacher_relationship():
    user = make_user("13910000001", "admin")
    grant_user_role(user, "admin")
    grant_user_role(user, "teacher")
    institution = make_institution()
    InstitutionMember.objects.create(
        institution=institution, user=user, role="teacher", status="active"
    )

    response = client_for(user, "admin").post(
        "/api/v1/classes",
        {"institution_id": str(institution.id), "class_name": "Forbidden Class"},
        format="json",
    )

    assert response.status_code == 403
    assert not Class.objects.filter(class_name="Forbidden Class").exists()


def test_teacher_session_cannot_use_platform_admin_endpoint():
    user = make_user("13910000002", "admin")
    grant_user_role(user, "admin")
    grant_user_role(user, "teacher")

    response = client_for(user, "teacher").post(
        "/api/v1/admin/institutions",
        {"institution_name": "Forbidden Platform School"},
        format="json",
    )

    assert response.status_code == 403
    assert not Institution.objects.filter(
        institution_name="Forbidden Platform School"
    ).exists()


def test_institution_admin_membership_does_not_grant_platform_admin():
    user = make_user("13910000003", "teacher")
    grant_user_role(user, "teacher")
    institution = make_institution()
    InstitutionMember.objects.create(
        institution=institution, user=user, role="admin", status="active"
    )

    response = client_for(user, "teacher").post(
        "/api/v1/admin/institutions",
        {"institution_name": "Escalated School"},
        format="json",
    )

    assert response.status_code == 403
    assert not has_user_role(user, "admin")


def test_approving_join_grants_student_without_removing_admin():
    teacher = make_user("13910000004", "teacher")
    grant_user_role(teacher, "teacher")
    institution = make_institution()
    InstitutionMember.objects.create(
        institution=institution, user=teacher, role="teacher", status="active"
    )
    class_obj = make_class(institution, teacher)
    ClassTeacher.objects.create(class_obj=class_obj, teacher=teacher, role="owner")

    applicant = make_user("13910000005", "admin")
    grant_user_role(applicant, "admin")
    join_request = ClassJoinRequest.objects.create(
        class_obj=class_obj,
        applicant=applicant,
        applicant_name=applicant.display_name,
        applicant_phone=applicant.mobile,
        request_type="self_apply",
        status="pending",
    )

    response = client_for(teacher, "teacher").post(
        f"/api/v1/classes/join-requests/{join_request.id}/approve", {}, format="json"
    )

    assert response.status_code == 200
    assert has_user_role(applicant, "student")
    assert has_user_role(applicant, "admin")


def test_direct_join_by_code_grants_student_role():
    teacher = make_user("13910000006", "teacher")
    institution = make_institution()
    class_obj = make_class(institution, teacher)
    student = make_user("13910000007", "parent")
    grant_user_role(student, "parent")
    client = APIClient()
    client.force_authenticate(user=student)

    response = client.post(
        "/api/v1/student/classes/join-by-code",
        {
            "invite_code": class_obj.invite_code,
            "applicant_name": student.display_name,
            "applicant_phone": student.mobile,
        },
        format="json",
    )

    assert response.status_code == 201
    assert has_user_role(student, "student")
    assert has_user_role(student, "parent")


def test_active_class_student_save_grants_student_idempotently():
    teacher = make_user("13910000008", "teacher")
    class_obj = make_class(make_institution(), teacher)
    student = make_user("13910000009", "admin")
    grant_user_role(student, "admin")

    relation = ClassStudent.objects.create(
        class_obj=class_obj, student=student, join_type="manual", status="active"
    )
    relation.save(update_fields=["status"])

    assert has_user_role(student, "student")
    assert has_user_role(student, "admin")
    assert student.role_grants.filter(role="student").count() == 1


def test_activating_parent_bind_grants_both_sides_idempotently():
    student = make_user("13910000010", "admin")
    parent = make_user("13910000011", "teacher")
    grant_user_role(student, "admin")
    grant_user_role(parent, "teacher")

    relation = StudentParentBind.objects.create(
        student_user_id=student,
        parent_user_id=parent,
        relation_type="guardian",
        bind_status="pending",
    )
    assert not has_user_role(student, "student")
    assert not has_user_role(parent, "parent")

    relation.bind_status = "active"
    relation.save(update_fields=["bind_status"])
    relation.save(update_fields=["bind_status"])

    assert has_user_role(student, "student")
    assert has_user_role(parent, "parent")
    assert has_user_role(student, "admin")
    assert has_user_role(parent, "teacher")
    assert student.role_grants.filter(role="student").count() == 1
    assert parent.role_grants.filter(role="parent").count() == 1


def test_targeted_mission_includes_student_grant_with_admin_legacy_role():
    teacher = make_user("13910000012", "teacher")
    student = make_user("13910000013", "admin")
    grant_user_role(student, "student")
    mission = LearningMission.objects.create(
        mission_name="Targeted Mission",
        creator_teacher_id=teacher,
        target_student_ids=[str(student.id)],
    )

    assert list(_mission_student_ids(mission)) == [student.id]


def test_class_mission_pdf_query_includes_teacher_legacy_multi_role_student():
    teacher = make_user("13910000014", "teacher")
    institution = make_institution()
    class_obj = make_class(institution, teacher)
    student = make_user("13910000015", "teacher")
    grant_user_role(student, "student")
    ClassStudent.objects.create(
        class_obj=class_obj, student=student, join_type="manual", status="active"
    )
    mission = LearningMission.objects.create(
        mission_name="Class Mission",
        creator_teacher_id=teacher,
        class_obj=class_obj,
    )

    assert _mission_students(mission) == [student]
