"""AI generation and deterministic fallbacks for classroom feedback."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable

from apps.common.ai import PromptRegistry
from apps.common.ai.client import AIClient
from apps.common.ai.response_parser import ResponseParser


CLASS_TASK = 'classroom_feedback_class_summary'
STUDENT_TASK = 'classroom_feedback_student_script'
MODEL_NAME = 'qwen3.7-flash'


def input_fingerprint(context: dict) -> str:
    payload = {key: value for key, value in context.items() if key != 'input_fingerprint'}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'),
    ).hexdigest()


def _clean(value, limit=300):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:limit]


def _list(value):
    return [item for item in value if _clean(item)] if isinstance(value, list) else []


def _validate_result(result, allowed_points, required_tokens=()):
    """Validate the response contract without blocking knowledge-point inference.

    ``allowed_points`` contains labels already present in the question bank.  It
    is only a hint: classroom feedback is explicitly expected to infer more
    specific concepts from the stem, answer and analysis, especially when the
    stored label is ``待归类题目``.  Treating that hint as a closed whitelist
    caused valid AI summaries such as “内能”和“比热容” to be discarded.
    """
    if not isinstance(result, dict):
        raise ValueError('AI 返回必须是 JSON 对象')
    text = _clean(result.get('feedback_text'), 2000)
    if len(text) < 12:
        raise ValueError('AI 反馈话术为空或过短')
    focus_points = [_clean(item, 255) for item in _list(result.get('focus_points'))]
    if required_tokens and not any(token and token in text for token in required_tokens):
        raise ValueError('AI 反馈未引用学生真实错题或知识点')
    return {
        'strengths': [_clean(item, 255) for item in _list(result.get('strengths'))[:5]],
        'focus_points': focus_points[:8],
        'action_suggestions': [_clean(item, 300) for item in _list(result.get('action_suggestions'))[:8]],
        'feedback_text': text,
        'confidence': max(0, min(1, float(result.get('confidence', 0.5) or 0.5))),
    }


def generate_feedback(task_key: str, context: dict, *, client_factory: Callable | None = None):
    """Call the configured task and return validated JSON plus model metadata."""
    registry = PromptRegistry()
    variable = 'class_context_json' if task_key == CLASS_TASK else 'student_context_json'
    system, user = registry.render(
        task_key, **{variable: json.dumps(context, ensure_ascii=False)},
    )
    client = client_factory() if client_factory else AIClient()
    owns_client = client_factory is None
    try:
        response = client.complete(task_key, system=system, user=user)
        parsed = ResponseParser.parse_json(response.content)
        allowed = set(
            context.get('allowed_knowledge_points')
            or context.get('knowledge_points')
            or context.get('focus_points')
            or context.get('knowledge_summary')
            or []
        )
        required = context.get('required_tokens') or ()
        return _validate_result(parsed, allowed, required), response.model
    finally:
        if owns_client:
            client.close()


def class_fallback(context: dict) -> str:
    points = context.get('weak_knowledge_points') or ['本节课相关知识点']
    good = context.get('good_knowledge_points') or ['基础概念']
    focus = '、'.join(points[:4])
    return (
        f"各位家长好！本周我们完成了《{_clean(context.get('mission_name'), 120)}》练习检测。"
        f"从班级整体来看，同学们在{'、'.join(good[:3])}方面掌握较好，"
        f"但在{focus}以及高错误率题目上错误较集中。"
        "请督促孩子订正错题、写清错误原因并完成对应知识点练习，老师会在后续课堂继续检查。"
    )


def student_fallback(context: dict) -> str:
    name = _clean(context.get('student_name'), 50) or '同学'
    if not context.get('wrong_count'):
        return (
            f'{name}家长您好！本次{_clean(context.get("mission_name"), 120)}练习中，'
            '孩子本次未出现课堂错题，说明相关知识点掌握情况较好。建议继续保持认真审题、规范作答的习惯，'
            '并适当复习本节课内容，老师也会在后续课堂继续关注孩子的学习表现。'
        )
    numbers = '、'.join(str(item) for item in context.get('wrong_question_nos') or []) or '本次题目'
    points = '、'.join(context.get('knowledge_summary') or []) or '本节课相关知识点'
    actions = '；'.join(context.get('review_arrangement') or [])
    return (
        f"{name}家长您好！本次《{_clean(context.get('mission_name'), 120)}》练习中，"
        f"{name}共错{int(context.get('wrong_count') or 0)}道，题号为{numbers}，主要涉及{points}。"
        f"建议先完成订正并复习相关知识点，{actions or '再完成对应知识点练习。'}"
        "理解错因后继续巩固，相信孩子会逐步提高，老师也会在后续课堂持续关注。"
    )
