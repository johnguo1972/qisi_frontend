import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.institutions.models import Class, ClassTeacher, Institution
from apps.missions.models import LearningMission, MissionLevel
from apps.qrcode.models import PaperScanBatch


pytestmark = pytest.mark.django_db


def _client_for(user, active_role):
    client = APIClient()
    token = generate_tokens(user, active_role)["access_token"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def multi_role_teacher_context(monkeypatch):
    user = UserAccount.objects.create(
        mobile="13920000001",
        login_name="13920000001",
        display_name="Multi Role Teacher",
        role_type="admin",
    )
    grant_user_role(user, "admin")
    grant_user_role(user, "teacher")
    institution = Institution.objects.create(
        institution_name="Teacher Route School",
        created_by=user,
    )
    class_obj = Class.objects.create(
        institution=institution,
        class_name="Teacher Route Class",
        creator_teacher=user,
    )
    ClassTeacher.objects.create(class_obj=class_obj, teacher=user, role="owner")
    mission = LearningMission.objects.create(
        mission_name="Teacher Route Mission",
        creator_teacher_id=user,
        class_obj=class_obj,
    )
    level = MissionLevel.objects.create(
        mission=mission,
        level_no=1,
        level_name="Level 1",
        level_type="practice",
    )
    batch = PaperScanBatch.objects.create(mission=mission, operator=user)
    monkeypatch.setattr("apps.qrcode.views.wxacode_png", lambda *_: b"png")
    monkeypatch.setattr("apps.qrcode.views.qr_png", lambda *_: b"png")
    monkeypatch.setattr("apps.qrcode.views._paper_pdf", lambda *_: b"%PDF-test")
    return {
        "user": user,
        "class": class_obj,
        "mission": mission,
        "level": level,
        "batch": batch,
    }


MISSION_TEACHER_ROUTES = [
    ("get", lambda c: "/api/v1/missions/", None),
    ("post", lambda c: "/api/v1/missions/", {"mission_name": "Blocked"}),
    ("get", lambda c: f"/api/v1/missions/{c['mission'].id}", None),
    ("put", lambda c: f"/api/v1/missions/{c['mission'].id}", {"mission_name": "Blocked"}),
    ("delete", lambda c: f"/api/v1/missions/{c['mission'].id}/delete", None),
    ("post", lambda c: f"/api/v1/missions/{c['mission'].id}/levels", {}),
    ("post", lambda c: f"/api/v1/missions/{c['mission'].id}/levels/batch", {}),
    ("get", lambda c: f"/api/v1/missions/{c['mission'].id}/levels/{c['level'].id}", None),
    ("post", lambda c: f"/api/v1/missions/{c['mission'].id}/questions", {}),
    ("post", lambda c: f"/api/v1/missions/{c['mission'].id}/favorites", {}),
    ("get", lambda c: f"/api/v1/missions/{c['mission'].id}/export-pdf", None),
    ("get", lambda c: f"/api/v1/missions/{c['mission'].id}/grading", None),
    ("patch", lambda c: f"/api/v1/missions/{c['mission'].id}/grading/attempts/{uuid.uuid4()}", {}),
    ("post", lambda c: f"/api/v1/missions/{c['mission'].id}/grading/generate-variant", {}),
    ("post", lambda c: f"/api/v1/missions/{c['mission'].id}/publish", {}),
    ("post", lambda c: f"/api/v1/missions/{c['mission'].id}/clone", {}),
    ("post", lambda c: f"/api/v1/missions/{c['mission'].id}/clone-with-class", {"class_id": lambda c: str(c["class"].id)}),
    ("post", lambda c: "/api/v1/missions/guidance/start/", {}),
    ("post", lambda c: "/api/v1/missions/guidance/reply/missing-session/", {}),
]


QRCODE_TEACHER_ROUTES = [
    ("get", lambda c: f"/api/v1/missions/{c['mission'].id}/qrcode", None),
    ("get", lambda c: f"/api/v1/missions/{c['mission'].id}/qrcode/info", None),
    ("get", lambda c: f"/api/v1/missions/{c['mission'].id}/wxacode", None),
    ("get", lambda c: f"/api/v1/missions/{c['mission'].id}/paper-pdf", None),
    ("post", lambda c: f"/api/v1/missions/{c['mission'].id}/practice-sheet", {}),
    ("get", lambda c: f"/api/v1/classes/{c['class'].id}/student-codes", None),
    ("post", lambda c: "/api/v1/paper-scan/batches", {"mission_id": lambda c: str(c["mission"].id)}),
    ("post", lambda c: f"/api/v1/paper-scan/batches/{c['batch'].id}/pages", {}),
    ("get", lambda c: f"/api/v1/paper-scan/batches/{c['batch'].id}/summary", None),
    ("post", lambda c: f"/api/v1/paper-scan/batches/{c['batch'].id}/complete", {}),
]


def _resolve_payload(payload, context):
    if payload is None:
        return None
    return {
        key: value(context) if callable(value) else value
        for key, value in payload.items()
    }


@pytest.mark.parametrize(
    "method,path_builder,payload",
    MISSION_TEACHER_ROUTES + QRCODE_TEACHER_ROUTES,
)
def test_non_teacher_active_role_cannot_reuse_teacher_routes(
    multi_role_teacher_context,
    method,
    path_builder,
    payload,
):
    context = multi_role_teacher_context
    client = _client_for(context["user"], "admin")
    request = getattr(client, method)
    kwargs = {}
    resolved_payload = _resolve_payload(payload, context)
    if resolved_payload is not None:
        kwargs.update(data=resolved_payload, format="json")

    response = request(path_builder(context), **kwargs)

    assert response.status_code == 403


def test_teacher_active_role_can_use_mission_and_qrcode_workflows(
    multi_role_teacher_context,
):
    context = multi_role_teacher_context
    client = _client_for(context["user"], "teacher")

    assert client.get("/api/v1/missions/").status_code == 200
    assert client.get(
        f"/api/v1/missions/{context['mission'].id}"
    ).status_code == 200
    assert client.get(
        f"/api/v1/missions/{context['mission'].id}/qrcode/info"
    ).status_code == 200
    assert client.get(
        f"/api/v1/classes/{context['class'].id}/student-codes"
    ).status_code == 200
    created = client.post(
        "/api/v1/paper-scan/batches",
        {"mission_id": str(context["mission"].id)},
        format="json",
    )
    assert created.status_code == 200
    assert client.get(
        f"/api/v1/paper-scan/batches/{created.data['data']['batch_id']}/summary"
    ).status_code == 200


def test_teacher_cannot_create_scan_batch_for_another_teachers_mission(
    multi_role_teacher_context,
):
    context = multi_role_teacher_context
    other = UserAccount.objects.create(
        mobile="13920000002",
        login_name="13920000002",
        display_name="Other Teacher",
        role_type="teacher",
    )
    grant_user_role(other, "teacher")

    response = _client_for(other, "teacher").post(
        "/api/v1/paper-scan/batches",
        {"mission_id": str(context["mission"].id)},
        format="json",
    )

    assert response.status_code == 404
    assert not PaperScanBatch.objects.filter(
        mission=context["mission"], operator=other
    ).exists()
