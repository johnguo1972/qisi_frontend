from pathlib import Path
import re
from unittest.mock import MagicMock, patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / 'uniapp' / 'src' / 'api' / 'questions.ts'
COMPONENT_PATH = ROOT / 'uniapp' / 'src' / 'components' / 'QuestionAIControls.vue'
ANSWER_MODAL_PATH = ROOT / 'uniapp' / 'src' / 'components' / 'AiAnswerModal.vue'
QUESTION_EDIT_PATH = ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'question-edit.vue'
COURSE_PRACTICE_PATH = ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'course-practice.vue'
MISSION_CREATE_PATH = ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'mission-create.vue'
PHOTO_VIEWS_PATH = ROOT / 'apps' / 'study' / 'photo_views.py'
STUDY_RECEIVERS_PATH = ROOT / 'apps' / 'study' / 'receivers.py'
TEACHER_PAGES = {
    'review-list': ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'review-list.vue',
    'audit': ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'audit.vue',
    'bank': ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'bank.vue',
    'new-question': ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'new-question.vue',
    'course-practice': ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'course-practice.vue',
}


def read(path: Path) -> str:
    assert path.exists(), f'Missing required source file: {path.relative_to(ROOT)}'
    return path.read_text(encoding='utf-8')


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


def test_question_ai_controls_exposes_the_five_manual_actions():
    source = read(COMPONENT_PATH)
    labels = {
        'all': '一键全部 AI 处理',
        'probe': 'AI 探查',
        'A': 'A 模式',
        'B': 'B 模式',
        'C': 'C 模式',
    }
    for action, label in labels.items():
        assert re.search(
            rf'<button\b[^>]*@click="startAction\(\'{action}\'\)"[^>]*>{label}</button>',
            source,
        )


def test_question_ai_controls_explains_the_full_pipeline_scope():
    source = read(COMPONENT_PATH)
    assert '一键全部' in source
    assert '题目探查、知识点分析、读图、A/B/C 模式答案、DeepSeek 校验' in source


def test_question_ai_controls_has_required_props_and_events():
    source = read(COMPONENT_PATH)
    assert re.search(r'defineProps\s*<\s*\{[\s\S]*?visible\s*:\s*boolean', source)
    assert re.search(r'questionId\s*:\s*string\s*\|\s*number\s*\|\s*null', source)
    assert re.search(r"defineEmits\s*<\s*\{[\s\S]*?close[\s\S]*?completed", source)


def test_probe_api_and_manual_id_types_are_exported():
    source = read(API_PATH)
    assert re.search(r'export function aiProcessProbe\(questionId: string \| number\)', source)
    assert '/review/question/${questionId}/ai-process-probe/' in source
    assert re.search(r'export function aiProcessQuestion\(questionId: string \| number\)', source)
    assert re.search(r'export function aiProcessSingleMode\(questionId: string \| number, mode: string\)', source)


def test_action_dispatch_uses_the_exact_api_mapping():
    source = read(COMPONENT_PATH)
    assert re.search(r"action === 'all'[\s\S]*?aiProcessQuestion\(props.questionId\)", source)
    assert re.search(r"action === 'probe'[\s\S]*?aiProcessProbe\(props.questionId\)", source)
    for mode in ('A', 'B', 'C'):
        assert re.search(rf"action === '{mode}'[\s\S]*?aiProcessSingleMode\(props.questionId, '{mode}'\)", source)


def test_answer_modal_reprocesses_only_the_selected_mode_without_opening_controls():
    """The answer-modal retry must remain a background mode task, not a nested dialog."""
    source = read(ANSWER_MODAL_PATH)
    assert 'QuestionAIControls' not in source
    assert re.search(r'import\s*\{[^}]*questionApi[^}]*getAiTaskStatus[^}]*\}', source)
    body = function_body(source, 'reprocess')
    assert re.search(r'questionApi\.aiProcessMode\(props\.question\.id,\s*item\)', body)
    assert 'getAiTaskStatus' in source
    assert 'reprocessVisible' not in source
    assert 'reprocessAction' not in source


def test_processing_is_only_started_by_explicit_buttons():
    source = read(COMPONENT_PATH)
    assert len(re.findall(r'@click="startAction\(', source)) == 5
    assert 'onMounted' not in source
    for callback in re.findall(r'watch\s*\([\s\S]*?\}\)', source):
        assert not re.search(r'aiProcess(?:Question|Probe|SingleMode)', callback)
    assert len(re.findall(r'(?<!function )startAction\(', source)) == 5


def test_polling_handles_all_terminal_states_and_cleans_up():
    source = read(COMPONENT_PATH)
    for status in ('complete', 'partial', 'failed', 'skipped'):
        assert f"'{status}'" in source
    assert re.search(r"function handleClose\(\)[\s\S]*?clearInterval", source)
    assert re.search(r"onUnmounted\s*\(\s*\(\)\s*=>[\s\S]*?clearInterval", source)


def test_pending_start_request_is_invalidated_before_it_can_begin_polling():
    source = read(COMPONENT_PATH)
    assert re.search(r'let requestGeneration\s*=\s*0', source)
    assert re.search(r'function invalidatePendingRequest\(\)\s*\{\s*requestGeneration \+= 1', source)
    assert re.search(r'function handleClose\(\)[\s\S]*?invalidatePendingRequest\(\)', source)
    assert re.search(r'\(visible\)\s*=>\s*\{\s*if \(!visible\)\s*\{\s*invalidatePendingRequest\(\)', source)
    assert re.search(r'watch\s*\(\s*\(\)\s*=>\s*props\.questionId[\s\S]*?invalidatePendingRequest\(\)', source)
    assert re.search(r'onUnmounted[\s\S]*?isUnmounted\s*=\s*true[\s\S]*?invalidatePendingRequest\(\)', source)
    assert re.search(
        r'const questionId = props\.questionId[\s\S]*?const requestToken = \+\+requestGeneration[\s\S]*?'
        r'await[\s\S]*?if \(requestToken !== requestGeneration \|\| isUnmounted \|\| !props\.visible '
        r'\|\| props\.questionId !== questionId\) return[\s\S]*?activeTaskId\.value',
        source,
    )


@pytest.mark.parametrize('page_name,handler_name', [
    ('review-list', 'handleAiProcess'),
    ('audit', 'processAI'),
    ('bank', 'handleAiProcess'),
    ('new-question', 'handleAiProcess'),
])
def test_teacher_question_page_delegates_single_ai_processing_to_shared_controls(page_name: str, handler_name: str):
    source = read(TEACHER_PAGES[page_name])
    forbidden_calls = r'aiProcessQuestion|aiProcessSingleMode|aiProcessProbe|getAiTaskStatus|\.aiProcess\(|\.getTaskStatus\('
    assert re.search(
        r"import\s+QuestionAIControls\s+from\s+['\"]@/components/QuestionAIControls\.vue['\"]",
        source,
    )
    assert len(re.findall(r'<QuestionAIControls\b', source)) == 1
    assert re.search(
        r'<QuestionAIControls\b[^>]*:visible="showAiControls"[^>]*:question-id="selectedAiQuestionId"',
        source,
    )
    assert '@close="closeAiControls"' in source
    assert '@completed="handleAiCompleted"' in source
    assert re.search(r'selectedAiQuestionId\s*=\s*ref<\s*string\s*\|\s*number\s*\|\s*null\s*>\(null\)', source)
    assert re.search(r'showAiControls\s*=\s*ref\(false\)', source)

    body = function_body(source, handler_name)
    assert re.search(r'selectedAiQuestionId\.value\s*=\s*questionId|selectedAiQuestionId\.value\s*=\s*qId', body)
    assert re.search(r'showAiControls\.value\s*=\s*true', body)
    assert not re.search(forbidden_calls, body)

    close_body = function_body(source, 'closeAiControls')
    assert re.search(r'showAiControls\.value\s*=\s*false', close_body)
    assert re.search(r'selectedAiQuestionId\.value\s*=\s*null', close_body)
    assert 'loadQuestions()' in function_body(source, 'handleAiCompleted')

    for function_name in ('loadQuestions', 'loadPapers', 'loadTree', 'loadKnowledgeTree'):
        if re.search(rf'(?:async\s+)?function\s+{function_name}\b', source):
            assert not re.search(forbidden_calls, function_body(source, function_name)), function_name
    for lifecycle in ('onMounted', 'onLoad'):
        match = re.search(rf'{lifecycle}\s*\(\s*\(.*?=>\s*\{{', source, re.DOTALL)
        if match:
            assert not re.search(forbidden_calls, source[match.start():match.start() + 600]), lifecycle

    if page_name == 'review-list':
        assert 'handleModeAiProcess' not in source
        assert 'modeAiState' not in source
        assert 'aiProcessSingleMode' not in source
    if page_name == 'review-list':
        batch_handler = 'handleBatchAiProcess'
        assert re.search(rf'@click="{batch_handler}"', source)
        batch_body = function_body(source, batch_handler)
        assert re.search(r'if\s*\(ids\.length\s*===\s*0\)\s*return', batch_body)
        assert 'startBatchAiProcess(' in batch_body
        assert 'handleAiProcess(' not in batch_body
        assert 'showAiControls.value = true' not in batch_body


@pytest.mark.parametrize(
    ('page_name', 'timer_collection'),
    [
        ('review-list', 'aiPollTimers'),
    ],
)
def test_batch_ai_pollers_stop_and_refresh_for_every_terminal_status(
    page_name: str, timer_collection: str
):
    source = read(TEACHER_PAGES[page_name])
    poller = function_body(source, 'startBatchAiProcess')
    terminal = re.search(
        r'if\s*\((?P<condition>data\.status[\s\S]*?)\)\s*\{'
        r'(?P<body>[\s\S]*?)\n\s*loadQuestions\(\)\s*\n\s*\}',
        poller,
    )
    assert terminal, f'Missing terminal-status branch in {page_name}'
    condition = terminal.group('condition')
    body = terminal.group('body')
    for status in ('complete', 'partial', 'failed', 'skipped'):
        assert f"data.status === '{status}'" in condition
    assert 'clearInterval(timer)' in body
    assert f'{timer_collection}.findIndex' in body
    assert f'{timer_collection}.splice' in body
    assert re.search(
        r"data\.status === 'skipped'[\s\S]*?showToast\(\{\s*title:\s*`[^`]*(?:跳过|不存在)[^`]*`",
        body,
    )


def test_course_practice_submits_single_and_batch_ai_to_background_jobs_without_controls_modal():
    """课程练习入口只能创建持久后台作业，不得打开同步 AI 控制弹窗。"""
    source = read(COURSE_PRACTICE_PATH)
    assert 'QuestionAIControls' not in source
    assert 'showAiControls' not in source
    assert 'selectedAiQuestionId' not in source
    assert 'runSequentially' not in source
    assert 'aiProcessQuestion' not in source
    assert 'getAiTaskStatus' not in source

    single_body = function_body(source, 'handleAiProcess')
    assert 'questionApi.batchAi([questionId])' in single_body
    assert 'showToast' in single_body

    batch_body = function_body(source, 'batchAiProcess')
    assert 'if (ids.length === 0) return' in batch_body
    assert 'questionApi.batchAi(ids)' in batch_body
    assert 'startBackgroundAiJob' in batch_body

    assert re.search(r'getAiJobStatus:\s*\(jobId: string\)\s*=>\s*get<any>\(`?/review/ai-jobs/\$\{jobId\}/`?\)', read(API_PATH))


def test_mission_create_sends_null_for_an_optional_empty_start_time():
    """DRF DateTimeField rejects '', while an omitted start time is valid."""
    source = read(MISSION_CREATE_PATH)
    publish_body = function_body(source, 'publish')

    create_payload = re.search(
        r'missionApi\.create\(\{(?P<payload>[\s\S]*?)\}\)', publish_body
    )
    assert create_payload, 'Missing mission creation payload'
    assert re.search(
        r'start_at:\s*form\.value\.start_at\s*\|\|\s*null',
        create_payload.group('payload'),
    )


def test_question_edit_delegates_ai_processing_to_one_shared_control():
    source = read(QUESTION_EDIT_PATH)
    forbidden_calls = r'aiProcessQuestion|aiProcessSingleMode|aiProcessProbe|getAiTaskStatus'

    assert re.search(
        r"import\s+QuestionAIControls\s+from\s+['\"]@/components/QuestionAIControls\.vue['\"]",
        source,
    )
    assert len(re.findall(r'<QuestionAIControls\b', source)) == 1
    assert re.search(
        r'<QuestionAIControls\b[^>]*:visible="showAiControls"[^>]*:question-id="selectedAiQuestionId"',
        source,
    )
    assert '@close="closeAiControls"' in source
    assert '@completed="handleAiCompleted"' in source
    assert re.search(r'<button\b[^>]*@click="handleAiProcess"[^>]*>AI处理</button>', source)
    assert re.search(r'selectedAiQuestionId\s*=\s*ref<\s*string\s*\|\s*number\s*\|\s*null\s*>\(null\)', source)
    assert re.search(r'showAiControls\s*=\s*ref\(false\)', source)

    open_body = function_body(source, 'handleAiProcess')
    assert re.fullmatch(
        r'\s*selectedAiQuestionId\.value\s*=\s*question\.value\.id\s*'
        r'showAiControls\.value\s*=\s*true\s*',
        open_body,
    )
    close_body = function_body(source, 'closeAiControls')
    assert re.search(r'showAiControls\.value\s*=\s*false', close_body)
    assert re.search(r'selectedAiQuestionId\.value\s*=\s*null', close_body)
    completed_body = function_body(source, 'handleAiCompleted')
    assert 'loadQuestion(questionId)' in completed_body
    assert 'closeAiControls()' in completed_body

    assert '重解析' not in source
    assert 'reparseLoading' not in source
    assert 'handleReparse' not in source
    assert not re.search(forbidden_calls, source)
    for function_name in (
        'loadQuestion', 'handleSave', 'handleConfirm', 'handleBackToList',
        'handlePrevQuestion', 'handleNextQuestion',
    ):
        assert not re.search(forbidden_calls, function_body(source, function_name)), function_name


def test_study_creation_sources_describe_manual_ai_without_dispatch_code():
    photo_source = read(PHOTO_VIEWS_PATH)
    receiver_source = read(STUDY_RECEIVERS_PATH)

    assert '# AI 答案不会自动生成，需由用户在界面手动触发' in photo_source
    assert 'AI 答案自动生成' not in receiver_source
    assert '异步触发 AI 答案生成' not in photo_source
    assert 'single_generate_ai_answers.delay' not in photo_source
    assert 'single_generate_ai_answers.delay' not in receiver_source


def test_missing_manual_ai_target_is_logged_at_warning_without_content():
    from apps.review import tasks

    set_progress = MagicMock()
    with patch.object(tasks.logger, 'warning') as warning:
        result = tasks._skip_missing_question(set_progress, 'missing-question')

    assert result == {
        'status': 'skipped',
        'question_id': 'missing-question',
        'reason': 'question_not_found',
    }
    warning.assert_called_once_with(
        'AI processing skipped because question was not found',
        extra={
            'question_id': 'missing-question',
            'status': 'skipped',
            'reason': 'question_not_found',
        },
    )
    assert 'content' not in warning.call_args.kwargs['extra']
