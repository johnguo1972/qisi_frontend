"""Integration tests for the 6-step AI processing pipeline."""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import pytest
from apps.common.ai_service import AIReviewService
from apps.common.ai_prompts import AIPrompts


@pytest.mark.skipif(not os.environ.get('QWEN_API_KEY'), reason="No QWEN_API_KEY")
class TestAIPipeline:
    """Integration tests for the AI pipeline (requires API key)."""

    def test_prompts_generate(self):
        """Test that all 6 prompts generate valid system/user pairs."""
        # Step 1: Probe & Norm
        probe = AIPrompts.probe_and_norm("题目内容")
        assert 'system' in probe and 'user' in probe

        # Step 2: Vision Extraction
        vision = AIPrompts.vision_extraction("规范化题干")
        assert 'system' in vision and 'user' in vision

        # Step 3a: Mode A Solver
        solver_a = AIPrompts.solve_mode_a("题干", '{"figure_present": true}')
        assert 'system' in solver_a and 'user' in solver_a

        # Step 3b: Mode B Solver
        solver_b = AIPrompts.solve_mode_b("题干", '{"figure_present": true}')
        assert 'system' in solver_b and 'user' in solver_b

        # Step 3c: Mode C Solver
        solver_c = AIPrompts.solve_mode_c("题干", '{"figure_present": true}')
        assert 'system' in solver_c and 'user' in solver_c

        # Step 4: Verifier
        verifier = AIPrompts.verify_result("题干", {}, {})
        assert 'system' in verifier and 'user' in verifier

    def test_oss_service_available(self):
        """Test that OSS service can be imported."""
        from apps.common.oss_service import upload_crop_image_safe
        assert callable(upload_crop_image_safe)

    def test_service_instantiation(self):
        """Test that AIReviewService can be instantiated."""
        service = AIReviewService()
        assert service is not None
        assert service.api_key != ''
