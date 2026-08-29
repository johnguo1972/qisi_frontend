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
    assert "response.data.user.active_role" in source
    assert "res.data.user.role_type" not in source
    assert "function navigateByRole" not in source
    assert "该帐号未开通此角色" in source
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


def test_student_role_switcher_is_available_on_h5_and_app_but_not_duplicated_in_mp():
    source = read("components/StudentSidebar.vue")

    assert "#ifndef MP-WEIXIN" in source
    assert "#ifdef H5" not in source


def test_wechat_login_and_bind_preserve_the_selected_role_route():
    wechat_api = read("api/wechat.ts")
    wechat_auth = read("utils/wechat-auth.ts")
    login = read("pages/login/index.vue")
    bind = read("pages/student/parent-bind.vue")

    assert "role_type: roleType" in wechat_api
    assert "wxLogin(activeTab.value)" in login
    assert "wechatApi.login(code, roleType)" in wechat_auth
    assert "routeForRole" in bind
    assert "response.data.user.active_role" in bind


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


def test_teacher_course_cards_have_a_registered_detail_page():
    course_list = read("pages/teacher/course-list.vue")
    course_detail = read("pages/teacher/course-detail.vue")
    pages = read("pages.json")

    assert "pages/teacher/course-detail?id=${course.id}" in course_list
    assert "pages/teacher/course-detail" in pages
    assert "courseApi.detail(courseId.value)" in course_detail
    assert "treeApi.list(courseId.value)" in course_detail
    assert "课程详情页开发中" not in course_list


def test_h5_app_role_menu_navigation_returns_to_layout_and_preserves_mp_routes():
    navigation = read("utils/role-navigation.ts")
    app = read("App.vue")
    teacher_layout = read("pages/teacher/layout.vue")
    student_layout = read("pages/student/layout.vue")
    parent_layout = read("pages/parent/layout.vue")
    parent_shell = read("components/ParentShell.vue")
    course_practice = read("pages/teacher/course-practice.vue")

    assert "uni.reLaunch({ url: roleSectionPath(role, section) })" in navigation
    assert "onLoad((options: any)" in teacher_layout
    assert "onLoad((options: any)" in student_layout
    assert "onLoad((options: any)" in parent_layout
    assert "navigateRoleSection('parent', key)" in parent_shell
    assert "// #ifdef MP-WEIXIN" in parent_shell
    assert "navigateRoleSection('teacher', page)" in course_practice
    assert "// #ifndef MP-WEIXIN" in course_practice
    assert "const isLoginEntry" in app
    assert "不覆盖用户直接打开的业务详情页" in app


def test_teacher_practice_course_info_api_is_explicitly_imported():
    source = read("pages/teacher/course-practice.vue")

    assert "courseApi" in source.split("\n", 30)[-1] or "import { courseApi" in source
    assert "courseApi.detail(courseId.value)" in source
