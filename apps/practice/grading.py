"""Pure answer validation and grading for personal practice attempts."""
from __future__ import annotations

import re


SUBJECTIVE_TYPES = {'short_answer', 'essay', 'computation', 'proof'}
OBJECTIVE_TYPES = {'single_choice', 'multiple_choice', 'true_false', 'fill_blank'}


class AnswerFormatError(ValueError):
    """The submitted answer does not match the question type contract."""


def _normalize_text(value) -> str:
    text = value.strip().replace(' ', '').replace('　', '').lower()
    return ''.join(
        chr(ord(char) - 0xFEE0) if 0xFF01 <= ord(char) <= 0xFF5E else char
        for char in text
    )


def _selected_options(answer_content):
    selected = answer_content.get('selected_options')
    if not isinstance(selected, (list, tuple, set)):
        raise AnswerFormatError('selected_options 必须是数组')
    values = {str(value).strip().upper() for value in selected if str(value).strip()}
    if not values:
        raise AnswerFormatError('请选择选项')
    return values


def _correct_options(question):
    correct = getattr(question, 'answer', '') or ''
    if not correct:
        ai_answer = getattr(question, 'ai_answer_a', None) or {}
        correct = ai_answer.get('answer', '') if isinstance(ai_answer, dict) else ''
    values = {char for char in str(correct).replace(' ', '').upper() if char.isalnum()}
    if not values:
        raise AnswerFormatError('题目没有可用的客观题答案')
    return values


def _fill_blank_result(question, answer_content):
    text = answer_content.get('text')
    if not isinstance(text, str):
        raise AnswerFormatError('填空题答案必须是 text 文本')
    correct = getattr(question, 'answer', '') or ''
    student_answers = [item for item in re.split(r'[；;，,、|]+', _normalize_text(text)) if item]
    correct_answers = [item for item in re.split(r'[；;，,、|]+', _normalize_text(str(correct))) if item]
    if not correct_answers:
        raise AnswerFormatError('题目没有可用的填空答案')
    return student_answers == correct_answers


def grade_question(question, answer_content):
    """Return ``(is_correct, is_subjective_pending)`` without database writes."""
    if not isinstance(answer_content, dict):
        raise AnswerFormatError('answer_content 必须是对象')
    question_type = question.question_type
    if question_type in {'single_choice', 'multiple_choice'}:
        selected = _selected_options(answer_content)
        if question_type == 'single_choice' and len(selected) != 1:
            raise AnswerFormatError('单选题只能选择一个选项')
        return selected == _correct_options(question), False
    if question_type == 'true_false':
        selected = answer_content.get('selected')
        if not isinstance(selected, str) or not selected.strip():
            raise AnswerFormatError('判断题答案必须是 selected 文本')
        correct = getattr(question, 'answer', '') or ''
        if not str(correct).strip():
            raise AnswerFormatError('题目没有可用的判断题答案')
        return selected.strip().upper() == str(correct).strip().upper(), False
    if question_type == 'fill_blank':
        return _fill_blank_result(question, answer_content), False
    if question_type in SUBJECTIVE_TYPES or question_type not in OBJECTIVE_TYPES:
        text = answer_content.get('text')
        if not isinstance(text, str):
            raise AnswerFormatError('主观题答案必须是 text 文本')
        if not text.strip():
            raise AnswerFormatError('主观题答案不能为空')
        return None, True
    raise AnswerFormatError('不支持的题型')
