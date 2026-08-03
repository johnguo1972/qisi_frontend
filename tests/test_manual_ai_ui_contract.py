from pathlib import Path
import re

import pytest


ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / 'uniapp' / 'src' / 'api' / 'questions.ts'
COMPONENT_PATH = ROOT / 'uniapp' / 'src' / 'components' / 'QuestionAIControls.vue'
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
    for label in ('一键全部AI处理', 'AI探查', 'A模式', 'B模式', 'C模式'):
        assert label in source


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
    ('course-practice', 'handleAiProcess'),
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
    if page_name in ('review-list', 'course-practice'):
        batch_handler = 'handleBatchAiProcess' if page_name == 'review-list' else 'batchAiProcess'
        assert re.search(rf'@click="{batch_handler}"', source)
        batch_body = function_body(source, batch_handler)
        assert re.search(r'if\s*\(ids\.length\s*===\s*0\)\s*return', batch_body)
        assert 'showAiControls.value = true' not in batch_body
