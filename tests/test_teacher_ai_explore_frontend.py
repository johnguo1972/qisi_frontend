from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
QUESTION_BANK_PATH = ROOT / 'uniapp' / 'src' / 'pages' / 'teacher' / 'question-bank.vue'


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


def test_ai_explore_uses_probe_processing_without_changing_batch_ai_contract():
    source = QUESTION_BANK_PATH.read_text(encoding='utf-8')
    explore_body = function_body(source, 'handleAiExplore')
    batch_body = function_body(source, 'handleBatchAi')

    assert 'handleBatchAi(' not in explore_body
    assert 'questionApi.batchAi(' not in explore_body
    assert re.search(r'if\s*\(!selectedQuestionIds\.value\.length\)', explore_body)
    assert "title: '请先选择题目'" in explore_body
    assert re.search(
        r'await\s+Promise\.all\(\s*selectedQuestionIds\.value\.map\(\s*id\s*=>\s*'
        r'questionApi\.aiProcessProbe\(id\)\s*\)\s*\)',
        explore_body,
    )
    assert "title: 'AI探索任务已提交'" in explore_body
    assert "title: 'AI探索提交失败'" in explore_body

    assert re.search(
        r'questionApi\.batchAi\(selectedQuestionIds\.value,\s*model\)',
        batch_body,
    )
