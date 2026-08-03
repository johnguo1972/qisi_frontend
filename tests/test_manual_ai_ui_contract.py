from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / 'uniapp' / 'src' / 'api' / 'questions.ts'
COMPONENT_PATH = ROOT / 'uniapp' / 'src' / 'components' / 'QuestionAIControls.vue'


def read(path: Path) -> str:
    assert path.exists(), f'Missing required source file: {path.relative_to(ROOT)}'
    return path.read_text(encoding='utf-8')


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
