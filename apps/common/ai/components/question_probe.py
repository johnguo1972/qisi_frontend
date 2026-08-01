"""Question classification, knowledge analysis, and vision fact components."""

from __future__ import annotations

from .base import QuestionAIComponent, QuestionInput


class QuestionProbeComponent(QuestionAIComponent):
    task_key = "question_probe"

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "ocr_text": question.stem,
            "has_figure": bool(question.image_urls),
            "ocr_confidence": question.metadata.get("ocr_confidence", "unknown"),
        }

    def normalize(self, result: dict) -> dict:
        normalized = dict(result)
        normalized.setdefault("subject", "")
        normalized.setdefault(
            "question_type", normalized.get("question_style", "")
        )
        normalized.setdefault("grade", "")
        normalized.setdefault("semester", "")
        normalized.setdefault("chapter", "")
        normalized.setdefault(
            "difficulty", normalized.get("difficulty_est", "")
        )
        normalized.setdefault(
            "knowledge_points", normalized.get("topic_tags_top3", [])
        )
        normalized.setdefault(
            "question_style", normalized.get("question_type", "")
        )
        normalized.setdefault(
            "difficulty_est", normalized.get("difficulty", "")
        )
        normalized.setdefault(
            "topic_tags_top3", normalized.get("knowledge_points", [])
        )
        return normalized


class KnowledgeAnalysisComponent(QuestionAIComponent):
    task_key = "knowledge_analysis"

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "normalized_text": question.metadata.get(
                "normalized_text", question.stem
            ),
            "subject_hint": question.metadata.get("subject_hint", ""),
        }


class VisionExtractionComponent(QuestionAIComponent):
    task_key = "vision_fact_extract"

    def prompt_variables(self, question: QuestionInput) -> dict[str, object]:
        return {
            "normalized_text": question.metadata.get(
                "normalized_text", question.stem
            )
        }
