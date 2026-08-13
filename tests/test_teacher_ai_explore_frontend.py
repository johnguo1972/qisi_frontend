from pathlib import Path
import base64
import json
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
QUESTION_BANK_PATH = ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'question-bank.vue'
ROLES_PATH = ROOT / 'uniapp' / 'src' / 'utils' / 'roles.ts'
ADMIN_HOME_PATH = ROOT / 'uniapp' / 'src' / 'pages' / 'admin' / 'home.vue'
REQUEST_PATH = ROOT / 'uniapp' / 'src' / 'utils' / 'request.ts'


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


def test_role_helper_rejects_unknown_stored_role_without_navigation():
    result = run_role_helpers({'active_role': 'operator'}, 'admin')
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


def run_admin_lifecycle_scenario(scenario: str) -> dict:
    source = ADMIN_HOME_PATH.read_text(encoding='utf-8')
    loader = function_body(source, 'loadInstitutions').replace('catch (e: any)', 'catch (e)').replace('(res as any)', 'res')
    initializer = function_body(source, 'initializeAdminHome').replace('catch (e: any)', 'catch (e)')
    mounted = lifecycle_body(source, 'onMounted')
    shown = lifecycle_body(source, 'onShow')
    snapshot = function_body(source, 'sessionSnapshot')
    unchanged = function_body(source, 'sessionUnchanged')
    script = f"""
      const storage = {{ accessToken: 'admin-token', userInfo: {{ active_role: 'admin' }} }};
      const items = {{ value: [] }};
      const loading = {{ value: true }};
      const userInfo = {{ value: {{}} }};
      let profileCalls = 0;
      let listCalls = 0;
      const listArgs = [];
      const uni = {{
        getStorageSync: (key) => storage[key],
        showToast: () => {{}},
        reLaunch: () => {{}},
      }};
      const currentSessionRole = () => storage.userInfo?.active_role;
      const ensurePageRole = () => storage.userInfo?.active_role === 'admin';
      const userStore = {{ setUserInfo: (info) => {{ storage.userInfo = info; }} }};
      const authApi = {{ getProfile: async () => {{
        profileCalls += 1;
        await Promise.resolve();
        return {{ data: {{ active_role: 'admin' }} }};
      }} }};
      const institutionApi = {{ list: async (...args) => {{
        listCalls += 1;
        listArgs.push(args);
        await Promise.resolve();
        return {{ code: 0, data: {{ items: [] }} }};
      }} }};
      const output = console.log;
      console.log = () => {{}};
      console.error = () => {{}};
      let initializationPromise = null;
      let institutionsLoadPromise = null;
      let hasLoadedOnShow = false;
      const sessionSnapshot = () => {{{snapshot}}};
      const sessionUnchanged = (snapshot) => {{{unchanged}}};
      const loadInstitutions = async (silentError = false) => {{{loader}}};
      const initializeAdminHome = async () => {{{initializer}}};
      const mounted = async () => {{{mounted}}};
      const shown = async () => {{{shown}}};

      await Promise.all([mounted(), shown()]);
      const initialListCalls = listCalls;
      if ({json.dumps(scenario)} === 'subsequent') {{
        await shown();
      }} else if ({json.dumps(scenario)} === 'concurrent') {{
        await Promise.all([shown(), shown(), shown()]);
      }}
      output(JSON.stringify({{ initialListCalls, listCalls, profileCalls, listArgs }}));
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


def test_admin_first_entry_loads_institutions_exactly_once():
    result = run_admin_lifecycle_scenario('initial')
    assert result['initialListCalls'] == 1
    assert result['listCalls'] == 1


def test_later_admin_onshow_adds_exactly_one_institution_request():
    result = run_admin_lifecycle_scenario('subsequent')
    assert result['initialListCalls'] == 1
    assert result['listCalls'] == 2


def test_concurrent_admin_onshow_calls_share_one_additional_request():
    result = run_admin_lifecycle_scenario('concurrent')
    assert result['initialListCalls'] == 1
    assert result['listCalls'] == 2


def run_stale_admin_response_scenario(scenario: str) -> dict:
    source = ADMIN_HOME_PATH.read_text(encoding='utf-8')
    loader = function_body(source, 'loadInstitutions').replace('catch (e: any)', 'catch (e)').replace('(res as any)', 'res')
    initializer = function_body(source, 'initializeAdminHome').replace('catch (e: any)', 'catch (e)')
    snapshot = function_body(source, 'sessionSnapshot')
    unchanged = function_body(source, 'sessionUnchanged')
    script = f"""
      const storage = {{ accessToken: 'admin-token', userInfo: {{ active_role: 'admin' }} }};
      const items = {{ value: [] }};
      const loading = {{ value: true }};
      const userInfo = {{ value: {{}} }};
      let profileCalls = 0;
      let listCalls = 0;
      let resolveProfile;
      let resolveList;
      let rejectList;
      const toasts = [];
      const uni = {{ getStorageSync: (key) => storage[key], showToast: (toast) => toasts.push(toast), reLaunch: () => {{}} }};
      const currentSessionRole = () => storage.userInfo?.active_role;
      const ensurePageRole = () => storage.userInfo?.active_role === 'admin';
      const userStore = {{ setUserInfo: (info) => {{ storage.userInfo = info; }} }};
      const authApi = {{ getProfile: () => {{
        profileCalls += 1;
        if ({json.dumps(scenario)} === 'retry' && profileCalls === 1) return Promise.reject(new Error('network'));
        if ({json.dumps(scenario)} === 'retry') return Promise.resolve({{ data: {{ active_role: 'admin' }} }});
        return new Promise((resolve) => {{ resolveProfile = resolve; }});
      }} }};
      const institutionApi = {{ list: () => {{
        listCalls += 1;
        if ({json.dumps(scenario)} === 'profile') return Promise.resolve({{ code: 0, data: {{ items: [] }} }});
        if ({json.dumps(scenario)} === 'retry') return Promise.resolve({{ code: 0, data: {{ items: [] }} }});
        if ({json.dumps(scenario)} === 'envelope') return Promise.resolve({{ code: 403, message: '', detail: '会话权限已变化', data: {{ items: ['new-item'] }} }});
        return new Promise((resolve, reject) => {{ resolveList = resolve; rejectList = reject; }});
      }} }};
      console.log = () => {{}}; console.error = () => {{}};
      let initializationPromise = null;
      let institutionsLoadPromise = null;
      const sessionSnapshot = () => {{{snapshot}}};
      const sessionUnchanged = (snapshot) => {{{unchanged}}};
      const loadInstitutions = async (silentError = false) => {{{loader}}};
      const initializeAdminHome = async () => {{{initializer}}};
      if ({json.dumps(scenario)} === 'profile') {{
        const stale = initializeAdminHome();
        await Promise.resolve();
        storage.accessToken = 'teacher-token'; storage.userInfo = {{ active_role: 'teacher' }};
        resolveProfile({{ data: {{ active_role: 'admin' }} }});
        await stale;
      }} else if ({json.dumps(scenario)} === 'list') {{
        const pending = loadInstitutions();
        while (!resolveList) await Promise.resolve();
        storage.accessToken = 'teacher-token'; storage.userInfo = {{ active_role: 'teacher' }};
        resolveList({{ code: 0, data: {{ items: ['old-admin-item'] }} }});
        await pending;
      }} else if ({json.dumps(scenario)} === 'list_error') {{
        const pending = loadInstitutions();
        while (!rejectList) await Promise.resolve();
        storage.accessToken = 'teacher-token'; storage.userInfo = {{ active_role: 'teacher' }};
        rejectList(new Error('old admin request failed'));
        await pending;
      }} else if ({json.dumps(scenario)} === 'envelope') {{
        items.value = ['existing-admin-item'];
        await loadInstitutions(true);
      }} else {{
        await initializeAdminHome();
        await initializeAdminHome();
      }}
      process.stdout.write(JSON.stringify({{ profileCalls, listCalls, role: storage.userInfo.active_role, token: storage.accessToken, items: items.value, loading: loading.value, toasts }}));
    """
    result = subprocess.run(['node', '--input-type=module', '--eval', script], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout)


def test_stale_profile_response_does_not_restore_old_admin_session():
    result = run_stale_admin_response_scenario('profile')
    assert result['profileCalls'] == 1
    assert result['listCalls'] == 0
    assert result['role'] == 'teacher'
    assert result['token'] == 'teacher-token'
    assert result['items'] == []


def test_stale_institution_response_does_not_write_admin_items():
    result = run_stale_admin_response_scenario('list')
    assert result['items'] == []
    assert result['role'] == 'teacher'


def test_failed_profile_initialization_can_retry():
    result = run_stale_admin_response_scenario('retry')
    assert result['profileCalls'] == 2


def run_request_error_scenarios() -> dict:
    source = REQUEST_PATH.read_text(encoding='utf-8')
    source = "const BASE_URL = '/api/v1'\n" + source[source.index('const requestLogs'):]
    source = re.sub(r'interface ApiResponse[\s\S]*?\n}\n\ninterface RequestError[\s\S]*?\n}\n', '', source)
    source = re.sub(r'<T>', '', source)
    source = re.sub(r': Promise<ApiResponse>', '', source)
    source = re.sub(r': \'GET\' \| \'POST\' \| \'PUT\' \| \'PATCH\' \| \'DELETE\'', '', source)
    source = source.replace('method as any', 'method').replace('parsed as ApiResponse', 'parsed').replace('err as any', 'err')
    source = source.replace('(globalThis as any)', 'globalThis')
    source = source.replace(': RequestOptions', '')
    source = source.replace('options?', 'options')
    source = source.replace('url: string', 'url').replace('data?: object', 'data')
    source = re.sub(r': Array<[^>]+>', '', source)
    source = re.sub(r': string\[\]', '', source)
    source = re.sub(r': RequestError', '', source)
    source = re.sub(r'export const (get|post|put|patch|del) =', r'const \1 =', source)
    source = source.replace('(url, data)', '(url, data, options)')
    script = f"""
      const events = [];
      let response = {{ kind: 'status', statusCode: 403 }};
      const uni = {{
        getStorageSync: () => 'token', removeStorageSync: (key) => events.push(['remove', key]),
        reLaunch: (arg) => events.push(['relaunch', arg.url]), showToast: () => events.push(['toast']),
        showModal: () => events.push(['modal']),
        request: (options) => {{
          if (response.kind === 'fail') options.fail({{ errMsg: 'offline' }});
          else options.success({{ statusCode: response.statusCode, data: {{}} }});
        }},
      }};
      {source}
      const run = async () => {{
        response = {{ kind: 'status', statusCode: 403 }}; events.length = 0;
        const default403Value = await get('/x'); const default403 = [...events];
        response = {{ kind: 'status', statusCode: 403 }}; events.length = 0;
        const silent403Value = await get('/x', undefined, {{ silentError: true }}); const silent403 = [...events];
        response = {{ kind: 'fail' }}; events.length = 0;
        let defaultFailError; try {{ await get('/x') }} catch (error) {{ defaultFailError = error }} const defaultFail = [...events];
        response = {{ kind: 'fail' }}; events.length = 0;
        let silentFailError; try {{ await get('/x', undefined, {{ silentError: true }}) }} catch (error) {{ silentFailError = error }} const silentFail = [...events];
        response = {{ kind: 'status', statusCode: 401 }}; events.length = 0;
        get('/x', undefined, {{ silentError: true }}); const silent401 = [...events];
        console.log(JSON.stringify({{ default403, default403Value, silent403, silent403Value, defaultFail, defaultFailError, silentFail, silentFailError, silent401 }}));
      }};
      await run();
    """
    result = subprocess.run(['node', '--input-type=module', '--eval', script], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    return json.loads(result.stdout.splitlines()[-1])


def test_request_silent_error_suppresses_only_global_error_ui_and_keeps_401_cleanup():
    calls = run_request_error_scenarios()
    assert calls['default403'] == [['toast']]
    assert calls['default403Value'] == {}
    assert calls['silent403'] == []
    assert calls['silent403Value'] == {}
    assert calls['defaultFail'] == [['modal']]
    assert calls['defaultFailError'] == {'errMsg': 'offline'}
    assert calls['silentFail'] == []
    assert calls['silentFailError'] == {'errMsg': 'offline'}
    assert calls['silent401'] == [
        ['remove', 'accessToken'], ['remove', 'refreshToken'], ['remove', 'tokenExpiry'], ['relaunch', '/pages/login/index'],
    ]


def test_admin_lifecycle_requests_silently_but_subsequent_refresh_is_also_silent():
    result = run_admin_lifecycle_scenario('subsequent')
    assert result['listArgs'] == [
        [None, {'silentError': True}],
        [None, {'silentError': True}],
    ]


def run_institution_list_options() -> list[list[object]]:
    source = (ROOT / 'uniapp' / 'src' / 'api' / 'institutions.ts').read_text(encoding='utf-8')
    list_start = source.index('  list: (')
    body_start = source.index('=> {', list_start) + len('=> {')
    depth = 1
    index = body_start
    while depth:
        if source[index] == '{':
            depth += 1
        elif source[index] == '}':
            depth -= 1
        index += 1
    body = source[body_start:index - 1]
    body = re.sub(r'get<\{[\s\S]*?\}>\(', 'get(', body)
    script = f"""
      const calls = [];
      const get = (...args) => {{ calls.push(args); return Promise.resolve({{}}); }};
      const list = (params, options) => {{{body}}};
      await list(undefined, {{ silentError: true }});
      await list({{ name: 'demo' }});
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


def test_institution_list_forwards_request_options_to_the_real_get_wrapper():
    calls = run_institution_list_options()
    assert calls == [
        ['/admin/institutions', None, {'silentError': True}],
        ['/admin/institutions?name=demo', None, None],
    ]


def run_confirm_delete_refresh() -> dict:
    source = ADMIN_HOME_PATH.read_text(encoding='utf-8')
    body = function_body(source, 'confirmDelete').replace('catch (e: any)', 'catch (e)')
    script = f"""
      const refreshArgs = [];
      const calls = [];
      const uni = {{
        showModal: (options) => options.success({{ confirm: true }}),
        showToast: (toast) => calls.push(toast),
      }};
      const institutionApi = {{ remove: async (id) => calls.push(['remove', id]) }};
      const loadInstitutions = async (...args) => refreshArgs.push(args);
      const confirmDelete = async (inst) => {{{body}}};
      await confirmDelete({{ id: 'institution-1', institution_name: '示例机构' }});
      console.log(JSON.stringify({{ refreshArgs, calls }}));
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


def test_delete_refresh_keeps_the_default_non_silent_error_behavior():
    result = run_confirm_delete_refresh()
    assert result['refreshArgs'] == [[]]
    assert result['calls'] == [['remove', 'institution-1'], {'title': '删除成功', 'icon': 'success'}]


def test_stale_failed_institution_request_has_no_toast_or_loading_write():
    result = run_stale_admin_response_scenario('list_error')
    assert result['role'] == 'teacher'
    assert result['toasts'] == []
    assert result['loading'] is True


def test_current_admin_error_envelope_shows_page_toast_and_preserves_existing_items():
    result = run_stale_admin_response_scenario('envelope')
    assert result['role'] == 'admin'
    assert result['items'] == ['existing-admin-item']
    assert result['toasts'] == [
        {'title': '会话权限已变化', 'icon': 'none', 'duration': 3000},
    ]


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


def run_handler(
    name: str,
    selected_ids: list[str],
    model: str | None = None,
    probe_rejected: bool = False,
) -> dict:
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
      const aiProcessProbe = async (id) => {{
        calls.probe.push(id);
        if ({json.dumps(probe_rejected)}) throw new Error('probe rejected');
      }};
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


def test_ai_explore_rejected_probe_shows_failure_toast():
    calls = run_handler('handleAiExplore', ['first', 'second'], probe_rejected=True)

    assert calls['probe'] == ['first', 'second']
    assert calls['batch'] == []
    assert calls['toasts'] == [{'title': 'AI探索提交失败', 'icon': 'none'}]


def test_batch_ai_keeps_using_the_complete_batch_pipeline():
    calls = run_handler('handleBatchAi', ['first', 'second'], 'deepseek')

    assert calls['probe'] == []
    assert calls['batch'] == [[['first', 'second'], 'deepseek']]
    assert calls['toasts'] == [{'title': '批量AI任务已提交', 'icon': 'success'}]
