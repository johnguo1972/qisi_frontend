from pathlib import Path
import base64
import json
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
QUESTION_BANK_PATH = ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'question-bank.vue'
ROLES_PATH = ROOT / 'uniapp' / 'src' / 'utils' / 'roles.ts'
ADMIN_HOME_PATH = ROOT / 'uniapp' / 'src' / 'pages' / 'admin' / 'home.vue'


def run_role_helpers(user_info: dict | None, expected_role: str) -> dict:
    source = ROLES_PATH.read_text(encoding='utf-8')
    executable = re.sub(r'export type AppRole = [^\n]+\n', '', source)
    executable = executable.replace('export function ', 'function ')
    executable = re.sub(r': (?:AppRole(?: \| undefined)?|string|boolean|void|any)', '', executable)
    executable = executable.replace(' as AppRole | undefined', '')
    script = f"""
      const storage = {{ userInfo: {json.dumps(user_info)} }};
      const calls = [];
      const uni = {{
        getStorageSync: (key) => storage[key],
        reLaunch: (options) => calls.push(options),
        setStorageSync: () => {{}},
      }};
      {executable}
      console.log(JSON.stringify({{
        role: currentSessionRole(),
        allowed: ensurePageRole({json.dumps(expected_role)}),
        calls,
      }}));
    """
    result = subprocess.run(
        ['node', '--input-type=module', '--eval', script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        check=True,
    )
    return json.loads(result.stdout.splitlines()[-1])


def test_role_helper_prefers_active_role_over_legacy_role_type():
    result = run_role_helpers({'active_role': 'admin', 'role_type': 'teacher'}, 'admin')
    assert result == {'role': 'admin', 'allowed': True, 'calls': []}


def test_role_helper_falls_back_to_legacy_role_type():
    result = run_role_helpers({'role_type': 'teacher'}, 'teacher')
    assert result == {'role': 'teacher', 'allowed': True, 'calls': []}


def test_role_helper_redirects_mismatched_teacher_to_teacher_home():
    result = run_role_helpers({'active_role': 'teacher'}, 'admin')
    assert result == {'role': 'teacher', 'allowed': False, 'calls': [{'url': '/pages/teacher/layout'}]}


def test_role_helper_rejects_absent_role_without_navigation():
    result = run_role_helpers(None, 'admin')
    assert result == {'allowed': False, 'calls': []}


def lifecycle_body(source: str, hook: str) -> str:
    marker = f'{hook}(async () => {{'
    start = source.index(marker) + len(marker)
    depth = 1
    index = start
    while depth:
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
        index += 1
    return source[start:index - 1]


def run_admin_lifecycles(allowed: bool) -> list[str]:
    source = ADMIN_HOME_PATH.read_text(encoding='utf-8')
    mounted = lifecycle_body(source, 'onMounted')
    shown = lifecycle_body(source, 'onShow')
    mounted = re.sub(r'catch \(e: any\)', 'catch (e)', mounted)
    shown = re.sub(r'catch \(e: any\)', 'catch (e)', shown)
    script = f"""
      const calls = [];
      let hasLoadedOnShow = false;
      const ensurePageRole = () => {{ calls.push('guard'); return {json.dumps(allowed)}; }};
      const authApi = {{ getProfile: async () => {{ calls.push('profile'); return {{}}; }} }};
      const userInfo = {{ value: {{}} }};
      const userStore = {{ setUserInfo: () => {{}} }};
      const uni = {{ showToast: () => {{}} }};
      const loadInstitutions = async () => calls.push('institutions');
      const mounted = async () => {{{mounted}}};
      const shown = async () => {{{shown}}};
      await mounted();
      await shown();
      await shown();
      console.log(JSON.stringify(calls));
    """
    result = subprocess.run(
        ['node', '--input-type=module', '--eval', script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        check=True,
    )
    return json.loads(result.stdout.splitlines()[-1])


def test_admin_lifecycle_guards_requests_and_keeps_one_initial_load():
    source = ADMIN_HOME_PATH.read_text(encoding='utf-8')
    assert "import { ensurePageRole } from '@/utils/roles'" in source

    assert run_admin_lifecycles(True) == [
        'guard', 'profile', 'institutions',
        'guard',
        'guard', 'institutions',
    ]
    assert run_admin_lifecycles(False) == ['guard', 'guard', 'guard']


def function_body(source: str, name: str) -> str:
    match = re.search(rf'(?:async\s+)?function\s+{name}\s*\([^)]*\)\s*\{{', source)
    assert match, f'Missing handler: {name}'
    depth = 1
    index = match.end()
    while depth and index < len(source):
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
        index += 1
    assert depth == 0, f'Unclosed handler: {name}'
    return source[match.end():index - 1]


def run_handler(name: str, selected_ids: list[str], model: str | None = None) -> dict:
    source = QUESTION_BANK_PATH.read_text(encoding='utf-8')
    body = function_body(source, name)
    encoded_handler = base64.b64encode(
        ('return async function handler(model) {' + body + '}').encode('utf-8')
    ).decode('ascii')
    script = f"""
      const selectedQuestionIds = {{ value: {json.dumps(selected_ids)} }};
      const calls = {{ probe: [], batch: [], toasts: [] }};
      const questionApi = {{
        batchAi: async (ids, requestedModel) => calls.batch.push([ids, requestedModel]),
      }};
      const aiProcessProbe = async (id) => calls.probe.push(id);
      const uni = {{ showToast: (toast) => calls.toasts.push(toast) }};
      const handler = new Function(
        'selectedQuestionIds', 'questionApi', 'aiProcessProbe', 'uni',
        Buffer.from({json.dumps(encoded_handler)}, 'base64').toString('utf8')
      )(selectedQuestionIds, questionApi, aiProcessProbe, uni);
      await handler({json.dumps(model)});
      console.log(JSON.stringify(calls));
    """
    result = subprocess.run(
        ['node', '--input-type=module', '--eval', script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding='utf-8',
        check=True,
    )
    return json.loads(result.stdout)


def test_ai_explore_uses_named_probe_api_for_each_selected_question():
    source = QUESTION_BANK_PATH.read_text(encoding='utf-8')
    assert re.search(r'import\s*\{[^}]*\baiProcessProbe\b[^}]*\}\s*from\s*[\'\"]@/api/questions[\'\"]', source)

    calls = run_handler('handleAiExplore', ['first', 'second'])

    assert calls['probe'] == ['first', 'second']
    assert calls['batch'] == []
    assert calls['toasts'] == [{'title': 'AI探索任务已提交', 'icon': 'success'}]


def test_ai_explore_empty_selection_does_not_call_any_ai_api():
    calls = run_handler('handleAiExplore', [])

    assert calls['probe'] == []
    assert calls['batch'] == []
    assert calls['toasts'] == [{'title': '请先选择题目', 'icon': 'none'}]


def test_batch_ai_keeps_using_the_complete_batch_pipeline():
    calls = run_handler('handleBatchAi', ['first', 'second'], 'deepseek')

    assert calls['probe'] == []
    assert calls['batch'] == [[['first', 'second'], 'deepseek']]
    assert calls['toasts'] == [{'title': '批量AI任务已提交', 'icon': 'success'}]
