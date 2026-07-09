"""学生端引导：轻量 Qwen 调用（独立于教师端 _call_qwen）。"""
import os
import httpx

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