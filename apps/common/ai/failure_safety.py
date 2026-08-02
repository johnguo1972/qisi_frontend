"""Fixed, provider-independent failure contracts for AI boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from apps.common.exceptions import AIRequestError


@dataclass(frozen=True)
class SafeFailureContract:
    code: str
    message: str

    @property
    def detail(self) -> str:
        return f"{self.code}: {self.message}"


POSITION_DETECTION_FAILURE = SafeFailureContract(
    "POSITION_DETECTION_FAILED", "题目位置检测失败"
)
QUESTION_PARSE_FAILURE = SafeFailureContract(
    "QUESTION_PARSE_FAILED", "题目解析失败"
)
PAPER_PARSE_FAILURE = SafeFailureContract(
    "PAPER_PARSE_FAILED", "试卷解析失败"
)
QUESTION_REPARSE_FAILURE = SafeFailureContract(
    "QUESTION_REPARSE_FAILED", "题目重解析失败"
)
PAGE_REPARSE_FAILURE = SafeFailureContract(
    "PAGE_REPARSE_FAILED", "页面重解析失败"
)
PHOTO_RECOGNITION_FAILURE = SafeFailureContract(
    "PHOTO_RECOGNITION_FAILED", "图片识别失败"
)


def log_safe_failure(
    target_logger: logging.Logger, contract: SafeFailureContract
) -> None:
    """Log a stable code without exception info or untrusted values."""
    target_logger.error(
        "AI boundary failed: %s",
        contract.code,
        extra={"failure_code": contract.code},
    )


def new_safe_ai_error(contract: SafeFailureContract) -> AIRequestError:
    """Create a fresh error after the raw exception scope has ended."""
    return AIRequestError(contract.detail)
