"""Canonical question-type values and normalization helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable


CANONICAL_QUESTION_TYPES = (
    'single_choice', 'multiple_choice', 'fill_blank', 'true_false',
    'short_answer', 'question_answer', 'proof', 'experiment',
    'computation', 'drawing', 'essay',
)

QUESTION_TYPE_LABELS = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'fill_blank': '填空题',
    'true_false': '判断题',
    'short_answer': '简答题',
    'question_answer': '问答题',
    'proof': '证明题',
    'experiment': '实验题',
    'computation': '计算题',
    'drawing': '作图题',
    'essay': '作文题',
}

_UNKNOWN_QUESTION_TYPE = 'unknown'

_ALIASES = {
    'single_choice': {
        'single_choice', 'single choice', 'single-choice', '单选', '单选题',
        '单项选择', '单项选择题',
    },
    'multiple_choice': {
        'multiple_choice', 'multiple choice', 'multiple-choice', '多选', '多选题',
        '多项选择', '多项选择题', '不定项选择', '不定项选择题',
    },
    'fill_blank': {'fill_blank', 'fill blank', '填空', '填空题'},
    'true_false': {'true_false', 'true false', '判断', '判断题', '是非题'},
    'short_answer': {'short_answer', 'short answer', '简答', '简答题'},
    'question_answer': {'question_answer', 'question answer', '问答', '问答题'},
    'proof': {'proof', '证明', '证明题'},
    'experiment': {'experiment', '实验', '实验题', '探究题'},
    'computation': {
        'computation', 'calculation', 'calculate', '计算', '计算题', '运算题',
    },
    'drawing': {'drawing', 'draw', '作图', '作图题', '画图题'},
    'essay': {'essay', '作文', '作文题'},
}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ''


def _option_count(options: object) -> int:
    if isinstance(options, dict):
        return len(options)
    if isinstance(options, Iterable) and not isinstance(options, (str, bytes)):
        return sum(1 for _item in options)
    return 0


def _has_multiple_selected_answers(answer: str) -> bool:
    return len(set(re.findall(r'[A-Za-z]', answer.upper()))) > 1


def normalize_question_type(raw, *, stem, options, answer) -> str:
    """Map source data to the canonical taxonomy, or ``unknown`` if unresolved."""
    token = _text(raw).lower().replace('-', '_')
    for question_type, aliases in _ALIASES.items():
        if token in {alias.replace('-', '_') for alias in aliases}:
            return question_type

    stem_text = _text(stem)
    answer_text = _text(answer)
    option_count = _option_count(options)
    if option_count and _has_multiple_selected_answers(answer_text):
        return 'multiple_choice'
    if option_count:
        return 'single_choice'
    if any(keyword in stem_text for keyword in ('作图', '画图', '光路图', '图像')):
        return 'drawing'
    if any(keyword in stem_text for keyword in ('实验', '探究')):
        return 'experiment'
    if '证明' in stem_text:
        return 'proof'
    if any(keyword in stem_text for keyword in ('计算', '求解', '解方程', '阻值')):
        return 'computation'
    if any(keyword in stem_text for keyword in ('填空', '填入')):
        return 'fill_blank'
    if any(keyword in stem_text for keyword in ('判断', '对错', '是否正确')):
        return 'true_false'
    if any(keyword in stem_text for keyword in ('作文', '写作')):
        return 'essay'
    if '问答' in stem_text:
        return 'question_answer'
    if '简答' in stem_text:
        return 'short_answer'
    return _UNKNOWN_QUESTION_TYPE


def require_ai_question_type(value) -> str:
    """Return an AI result only when it is an exact canonical type."""
    if value not in CANONICAL_QUESTION_TYPES:
        raise ValueError('invalid_question_type')
    return value
