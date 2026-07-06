"""Feedback engine for gamification."""
import random

CORRECT_FEEDBACK = [
    "这步推导很漂亮，你已经抓住关键条件。",
    "正确！你的思路很清晰。",
    "做得好，继续保持这个状态。",
]

INCORRECT_FEEDBACK = [
    "你的思路方向对，但在公式选取上有偏差。再试一次？",
    "别灰心，这个知识点确实容易混淆。让我们换个角度思考。",
    "答案不对，但你已经接近了。再想想？",
]


def generate_feedback(is_correct: bool, question=None, attempt_no: int = 1) -> str:
    """Generate feedback text based on correctness and attempt count."""
    if is_correct:
        if attempt_no == 1:
            return "太棒了，一次就做对！"
        return random.choice(CORRECT_FEEDBACK)
    else:
        if attempt_no >= 3:
            return f"已经尝试了{attempt_no}次，建议进入引导模式重新思考。"
        return random.choice(INCORRECT_FEEDBACK)
