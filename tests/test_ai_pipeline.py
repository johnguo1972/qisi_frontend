"""Integration tests for the 6-step AI processing pipeline."""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import pytest
from apps.common.ai_service import AIReviewService
from apps.common.ai.prompt_registry import PromptRegistry


@pytest.mark.skipif(not os.environ.get('QWEN_API_KEY'), reason="No QWEN_API_KEY")
class TestAIPipeline:
    """Integration tests for the AI pipeline (requires API key)."""

    def test_prompts_generate(self):
        """All six pipeline prompts render from the central registry."""
        registry = PromptRegistry()
        cases = (
            (
                "question_probe",
                {"ocr_text": "题目内容", "has_figure": True,
                 "ocr_confidence": "unknown"},
            ),
            ("vision_fact_extract", {"normalized_text": "规范化题干"}),
            (
                "mode_a_answer",
                {"normalized_text": "题干", "vision_json": "{}",
                 "knowledge_refs": ""},
            ),
            (
                "mode_b_answer",
                {"normalized_text": "题干", "vision_json": "{}",
                 "knowledge_refs": ""},
            ),
            (
                "mode_c_answer",
                {"normalized_text": "题干", "vision_json": "{}",
                 "knowledge_refs": ""},
            ),
            (
                "result_verify",
                {"normalized_text": "题干", "vision_json": "{}",
                 "solver_output": "{}"},
            ),
        )

        for task_key, variables in cases:
            system, user = registry.render(task_key, **variables)
            assert system
            assert user

    def test_oss_service_available(self):
        """Test that OSS service can be imported."""
        from apps.common.oss_service import upload_crop_image_safe
        assert callable(upload_crop_image_safe)

    def test_service_instantiation(self):
        """The facade is usable without retaining provider credentials."""
        with AIReviewService() as service:
            assert service is not None
            assert not hasattr(service, 'api_key')
