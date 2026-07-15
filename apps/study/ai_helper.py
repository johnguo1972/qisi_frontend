"""学生端引导：轻量 Qwen 调用（独立于教师端 _call_qwen）。"""
import os
import json
import httpx
import logging

logger = logging.getLogger(__name__)

QWEN_API_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'


def call_qwen_for_guidance(system_prompt: str, user_prompt: str, model: str = 'qwen3.6-flash') -> str:
    """对学生回复做简短评价。失败返回安全兜底文案（不抛异常，不阻塞流程）。"""
    api_key = os.environ.get('QWEN_API_KEY', '')
    if not api_key:
        return '（AI 暂不可用）'
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {'model': model, 'messages': [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}],
        'max_tokens': 300, 'temperature': 0.7}
    try:
        with httpx.Client(timeout=60.0, trust_env=False) as client:
            resp = client.post(QWEN_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f'（AI 评价暂时不可用：{e.__class__.__name__}）'


GUIDANCE_GENERATE_SYSTEM_PROMPT = """你是一位擅长苏格拉底式教学的中学教师。
根据题目信息和学生可能的知识水平，设计3-5个递进式引导问题。
每个问题应引导学生自主思考，而非直接给出答案。

输出严格JSON格式，不要包含markdown代码块：
{
  "steps": [
    {"question": "第一个引导问题", "hint": "提示学生思考的方向"},
    {"question": "第二个引导问题", "hint": "进一步深入提示"}
  ]
}"""


def call_qwen_for_guidance_with_question(stem: str, answer: str = "") -> dict:
    """实时调用 LLM 生成引导问题，用于 C 模式 ai_answer_c 为空时的降级兜底。

    返回: {"steps": [{"question": "...", "hint": "..."}]} 或空 dict
    """
    api_key = os.environ.get('QWEN_API_KEY', '')
    if not api_key:
        logger.warning('QWEN_API_KEY not set, cannot generate guidance')
        return {}

    user_prompt = f"""请为以下题目设计引导问题：
题干：{stem}
答案：{answer or '见解析'}
请设计3-5个递进式引导问题，帮助学生自主思考。"""

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': 'qwen3.6-flash',
        'messages': [
            {'role': 'system', 'content': GUIDANCE_GENERATE_SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt},
        ],
        'max_tokens': 2000,
        'temperature': 0.7,
        'response_format': {'type': 'json_object'},
    }

    try:
        with httpx.Client(timeout=60.0, trust_env=False) as client:
            resp = client.post(QWEN_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content']
            result = json.loads(content)
            if result and isinstance(result, dict) and 'steps' in result:
                return result
            return {}
    except Exception as e:
        logger.warning(f'Guidance generation failed: {e}')
        return {}