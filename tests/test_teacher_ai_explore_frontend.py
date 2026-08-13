from pathlib import Path
import base64
import json
import re
import subprocess


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
