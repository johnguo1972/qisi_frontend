import pytest
from unittest.mock import patch
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
from apps.qrcode.models import WrongbookPracticeSheet
from apps.wrongbook.models import WrongBookItem


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
    grant_user_role(student, "student")
    client = client_for(student, "student")

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


def test_institution_admin_requires_teacher_session_and_grant():
    user = make_user("13910000016", "parent")
    grant_user_role(user, "parent")
    grant_user_role(user, "teacher")
    institution = make_institution()
    InstitutionMember.objects.create(
        institution=institution, user=user, role="admin", status="active"
    )

    assert client_for(user, "parent").get(
        f"/api/v1/institutions/{institution.id}/members"
    ).status_code == 403
    assert client_for(user, "teacher").get(
        f"/api/v1/institutions/{institution.id}/members"
    ).status_code == 200


@pytest.mark.parametrize("path,method,mobile", [
    ("/api/v1/student/classes/search", "post", "13910000101"),
    ("/api/v1/student/classes/join-by-code", "post", "13910000102"),
    ("/api/v1/classes/join-request", "post", "13910000103"),
    ("/api/v1/student/my-classes", "get", "13910000104"),
    ("/api/v1/student/join-requests", "get", "13910000105"),
])
def test_student_apis_reject_teacher_session(path, method, mobile):
    user = make_user(mobile, "teacher")
    grant_user_role(user, "teacher")
    grant_user_role(user, "student")

    response = getattr(client_for(user, "teacher"), method)(path, {}, format="json")

    assert response.status_code == 403


def test_student_search_allows_student_session_without_class_membership():
    user = make_user("13910000017", "teacher")
    grant_user_role(user, "student")

    response = client_for(user, "student").post(
        "/api/v1/student/classes/search", {"teacher_mobile": "13900009999"}, format="json"
    )

    assert response.status_code == 200


def make_wrong_item(student):
    return WrongBookItem.objects.create(student_user_id=student, question_id=student.id)


def test_unrelated_teacher_cannot_create_practice_sheet(monkeypatch):
    student = make_user("13910000018", "student")
    teacher = make_user("13910000019", "teacher")
    grant_user_role(teacher, "teacher")
    item = make_wrong_item(student)
    monkeypatch.setattr("apps.wrongbook.services.find_variant_questions", lambda *a, **k: [])

    response = client_for(teacher, "teacher").post(
        "/api/v1/practice-sheets", {"wrong_item_id": str(item.id)}, format="json"
    )

    assert response.status_code == 403


def test_related_teacher_can_create_practice_sheet_and_cannot_change_owner(monkeypatch):
    student = make_user("13910000020", "student")
    other = make_user("13910000021", "student")
    teacher = make_user("13910000022", "teacher")
    grant_user_role(teacher, "teacher")
    institution = make_institution()
    class_obj = make_class(institution, teacher)
    ClassTeacher.objects.create(class_obj=class_obj, teacher=teacher, role="owner")
    ClassStudent.objects.create(class_obj=class_obj, student=student, join_type="manual", status="active")
    item = make_wrong_item(student)
    monkeypatch.setattr("apps.wrongbook.services.find_variant_questions", lambda *a, **k: [])

    allowed = client_for(teacher, "teacher").post(
        "/api/v1/practice-sheets", {"wrong_item_id": str(item.id)}, format="json"
    )
    tampered = client_for(teacher, "teacher").post(
        "/api/v1/practice-sheets",
        {"wrong_item_id": str(item.id), "student_id": str(other.id)},
        format="json",
    )

    assert allowed.status_code == 201
    assert tampered.status_code == 400
    assert WrongbookPracticeSheet.objects.filter(student=other).count() == 0


def test_parent_children_requires_parent_session():
    user = make_user("13910000023", "teacher")
    grant_user_role(user, "teacher")
    grant_user_role(user, "parent")

    assert client_for(user, "teacher").get("/api/v1/parent/children").status_code == 403
    assert client_for(user, "parent").get("/api/v1/parent/children").status_code == 200


def test_practice_sheet_info_rejects_unrelated_user_and_allows_owner():
    student = make_user("13910000024", "student")
    stranger = make_user("13910000025", "student")
    grant_user_role(student, "student")
    grant_user_role(stranger, "student")
    item = make_wrong_item(student)
    sheet = WrongbookPracticeSheet.objects.create(
        student=student, wrong_item=item, sheet_code="ABC123", original_question_id=item.question_id
    )

    assert client_for(stranger, "student").get(f"/api/v1/practice-sheets/{sheet.sheet_code}").status_code == 403
    assert client_for(student, "student").get(f"/api/v1/practice-sheets/{sheet.sheet_code}").status_code == 200


def test_practice_sheet_info_allows_current_parent_related_teacher_and_platform_admin():
    from django.core.cache import cache

    student = make_user("13910000030", "student")
    parent = make_user("13910000031", "parent")
    teacher = make_user("13910000032", "teacher")
    admin = make_user("13910000033", "admin")
    for user, role in ((student, "student"), (parent, "parent"), (teacher, "teacher"), (admin, "admin")):
        grant_user_role(user, role)
    institution = make_institution()
    class_obj = make_class(institution, teacher)
    ClassTeacher.objects.create(class_obj=class_obj, teacher=teacher, role="owner")
    ClassStudent.objects.create(class_obj=class_obj, student=student, join_type="manual", status="active")
    StudentParentBind.objects.create(
        student_user_id=student, parent_user_id=parent, relation_type="guardian", bind_status="active"
    )
    cache.set(f"parent_context:{parent.id}", str(student.id), timeout=1800)
    item = make_wrong_item(student)
    sheet = WrongbookPracticeSheet.objects.create(
        student=student, wrong_item=item, sheet_code="XYZ789", original_question_id=item.question_id
    )

    for user, role in ((parent, "parent"), (teacher, "teacher"), (admin, "admin")):
        assert client_for(user, role).get(
            f"/api/v1/practice-sheets/{sheet.sheet_code}"
        ).status_code == 200


def test_class_student_grant_failure_rolls_back_relationship():
    teacher = make_user("13910000026", "teacher")
    student = make_user("13910000027", "admin")
    class_obj = make_class(make_institution(), teacher)

    with patch("apps.institutions.signals.grant_user_role", side_effect=RuntimeError("grant failed")):
        with pytest.raises(RuntimeError, match="grant failed"):
            ClassStudent.objects.create(
                class_obj=class_obj, student=student, join_type="manual", status="active"
            )

    assert not ClassStudent.objects.filter(class_obj=class_obj, student=student).exists()
    assert not has_user_role(student, "student")


def test_parent_bind_second_grant_failure_rolls_back_relation_and_first_grant():
    student = make_user("13910000028", "admin")
    parent = make_user("13910000029", "teacher")
    from apps.accounts.roles import grant_user_role as real_grant

    def fail_parent(user, role):
        if role == "parent":
            raise RuntimeError("parent grant failed")
        return real_grant(user, role)

    with patch("apps.accounts.signals.grant_user_role", side_effect=fail_parent):
        with pytest.raises(RuntimeError, match="parent grant failed"):
            StudentParentBind.objects.create(
                student_user_id=student,
                parent_user_id=parent,
                relation_type="guardian",
                bind_status="active",
            )

    assert not StudentParentBind.objects.filter(student_user_id=student, parent_user_id=parent).exists()
    assert not has_user_role(student, "student")
    assert not has_user_role(parent, "parent")
