"""Backward-compatible synchronous wrappers for shared guidance AI."""

import logging

from apps.common.ai.components import (
    GuidanceComponent,
    GuidanceContext,
    QuestionInput,
)
from apps.common.ai.exceptions import AIConfigError


logger = logging.getLogger(__name__)
guidance_component_factory = GuidanceComponent


def call_qwen_for_guidance(
    system_prompt: str,
    user_prompt: str,
    model: str = "qwen3.7-flash",
) -> str:
    """Preserve the old sync API while routing through the shared component."""
    del model
    try:
        return guidance_component_factory().evaluate_student_reply(
            GuidanceContext(
                question_text=system_prompt,
                student_answer=user_prompt,
            )
        )
    except AIConfigError:
        return "（AI 暂不可用）"
    except Exception as error:
        return f"（AI 评价暂时不可用：{error.__class__.__name__}）"


def call_qwen_for_guidance_with_question(
    stem: str, answer: str = ""
) -> dict:
    """Preserve the old generation API; all failures remain an empty dict."""
    try:
        return guidance_component_factory().generate(
            QuestionInput(stem=stem, answer=answer)
        )
    except Exception as error:
        logger.warning(
            "Guidance generation failed: %s", error.__class__.__name__
        )
        return {}
