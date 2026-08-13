from pathlib import Path
import json
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "uniapp" / "src"


def read(relative_path: str) -> str:
    return (SRC / relative_path).read_text(encoding="utf-8")


def test_login_uses_server_active_role_and_shared_route_helper():
    source = read("pages/login/index.vue")

    assert "routeForRole" in source
    assert "res.data.user.active_role" in source
    assert "res.data.user.role_type" not in source
    assert "function navigateByRole" not in source
    assert "该账号未开通此角色" in source
    assert "ROLE_NOT_GRANTED" in source


def test_auth_api_and_roles_utility_define_role_switch_session_contract():
    api = read("api/index.ts")
    roles = read("utils/roles.ts")

    assert "switchRole" in api
    assert "'/auth/switch-role'" in api
    assert "export function routeForRole" in roles
    for key in ("accessToken", "refreshToken", "userInfo"):
        assert f"setStorageSync('{key}'" in roles


def test_role_switcher_uses_only_granted_roles_and_persists_new_session():
    source = read("components/RoleSwitcher.vue")

    assert "userInfo.value.roles" in source
    assert "userInfo.active_role" in source
    assert "roles.length > 1" in source
    assert "authApi.switchRole" in source
    assert "persistSession" in source
    assert "userStore.setUserInfo" in source
    assert "routeForRole" in source
    assert "uni.reLaunch" in source


def test_all_required_surfaces_include_role_switcher():
    for relative_path in (
        "pages/admin/home.vue",
        "components/TeacherSidebar.vue",
        "components/StudentSidebar.vue",
        "components/MpDrawer.vue",
    ):
        assert "RoleSwitcher" in read(relative_path), relative_path


def test_app_uses_shared_server_active_role_route():
    source = read("App.vue")

    assert "routeForRole" in source
    assert "userInfo?.active_role || userInfo?.role_type" in source
    assert "function navigateByRole" not in source


def test_institution_member_ui_is_multi_role_and_teacher_fields_are_conditional():
    source = read("pages/admin/institution-detail.vue")

    assert "roles: [] as InstitutionRole[]" in source
    assert "m.roles" in source
    assert "v-for=\"role in m.roles\"" in source
    assert "机构管理员" in source
    assert "系统管理员" not in source
    assert "toggleEditRole" in source
    assert "editForm.value.roles.length" in source
    assert "roles: [...editForm.value.roles]" in source
    assert "roles.includes('teacher')" in source
    assert "移除成员" in source


def test_member_normalizers_execute_legacy_and_missing_role_cases():
    module_uri = (SRC / "utils" / "institution-members.ts").as_uri()
    script = f"""
      import {{ normalizeMember, normalizeRoles }} from {json.dumps(module_uri)};
      const legacy = normalizeMember({{ user_id: 'u1', role: 'admin' }});
      const missing = normalizeMember({{ user_id: 'u2' }});
      const filtered = normalizeRoles(['teacher', 'invalid', 'teacher'], 'admin');
      console.log(JSON.stringify({{ legacy, missing, filtered }}));
    """
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "--eval", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert data["legacy"]["roles"] == ["admin"]
    assert data["missing"]["roles"] == ["teacher"]
    assert data["filtered"] == ["teacher"]


def test_add_member_form_uses_roles_and_keeps_identity_fields_visible():
    source = read("pages/admin/institution-detail.vue")
    api = read("api/institutions.ts")

    assert "memberForm.value.roles.length === 0" in source
    assert "toggleMemberRole" in source
    assert "memberForm.roles.includes('teacher')" in source
    assert re.search(r"memberForm\.role(?!s)", source) is None
    assert "addMemberRoles" in source
    assert "addMemberRoles" in api
    assert "部分角色添加失败" in source
    assert '<view v-if="memberForm.roles.includes(\'teacher\')" class="form-row">' in source
    assert '<input v-model="memberForm.mobile"' in source


def test_member_load_path_normalizes_before_template_rendering():
    source = read("pages/admin/institution-detail.vue")

    assert "normalizeMember" in source
    assert ".map(normalizeMember)" in source
