"""Business logic for AI-powered review operations."""
import logging
from django.utils import timezone
from apps.parser.models import ExamQuestion
from apps.common.ai_service import AIReviewService
from apps.common.exceptions import AIRequestError

logger = logging.getLogger(__name__)


def process_single_question(question_id: int, model: str = None) -> dict:
    """Run full AI pipeline for a single question and save results.

    Returns a summary dict even if some steps fail.
    """
    service = AIReviewService()
    results = service.process_question_full(question_id, model=model)
    service.save_results_to_question(question_id, results)

    question = ExamQuestion.objects.get(id=question_id)
    return {
        'question_id': question_id,
        'knowledge_points_count': len(
            question.ai_knowledge_enrichment.get('knowledge_points', [])
        ) if question.ai_knowledge_enrichment else 0,
        'answer_a_generated': bool(question.ai_answer_a),
        'answer_b_generated': bool(question.ai_answer_b),
        'answer_c_generated': bool(question.ai_answer_c),
        'errors': results.get('errors', {}),
    }


def confirm_ai_answer(question_id: int, mode: str) -> dict:
    """Mark an AI answer as confirmed."""
    mode_field_map = {'A': 'ai_answer_a', 'B': 'ai_answer_b', 'C': 'ai_answer_c'}
    field = mode_field_map.get(mode)
    if not field:
        raise ValueError(f"Invalid mode: {mode}")

    question = ExamQuestion.objects.get(id=question_id)
    answer_data = getattr(question, field)
    if not answer_data:
        raise ValueError(f"No AI answer {mode} found for question {question_id}")

    answer_data['confirmed'] = True
    answer_data['confirmed_at'] = timezone.now().isoformat()
    setattr(question, field, answer_data)
    question.save(update_fields=[field])

    return {'success': True, 'mode': mode, 'confirmed_at': answer_data['confirmed_at']}


def update_ai_answer(question_id: int, mode: str, edited_content: dict) -> dict:
    """Save edited AI answer content."""
    mode_field_map = {'A': 'ai_answer_a', 'B': 'ai_answer_b', 'C': 'ai_answer_c'}
    field = mode_field_map.get(mode)
    if not field:
        raise ValueError(f"Invalid mode: {mode}")

    question = ExamQuestion.objects.get(id=question_id)
    answer_data = getattr(question, field)
    if not answer_data:
        raise ValueError(f"No AI answer {mode} found for question {question_id}")

    answer_data['edited_content'] = edited_content
    setattr(question, field, answer_data)
    question.save(update_fields=[field])

    return {'success': True, 'mode': mode}


def update_knowledge_enrichment(question_id: int, updated_data: dict) -> dict:
    """Save edited knowledge enrichment data."""
    question = ExamQuestion.objects.get(id=question_id)
    question.ai_knowledge_enrichment = updated_data
    question.save(update_fields=['ai_knowledge_enrichment'])
    return {'success': True}


def get_ai_status(question_id: int) -> dict:
    """Get AI processing status for a question."""
    question = ExamQuestion.objects.get(id=question_id)

    def count_kp(data):
        if not data:
            return 0
        return len(data.get('knowledge_points', []))

    def get_mode_status(data):
        if not data:
            return 'blank'
        if data.get('error'):
            return 'error'
        if data.get('confirmed'):
            return 'confirmed'
        return 'unconfirmed'

    return {
        'question_id': question_id,
        'knowledge_points_count': count_kp(question.ai_knowledge_enrichment),
        'knowledge_enrichment': question.ai_knowledge_enrichment,
        'answer_a_status': get_mode_status(question.ai_answer_a),
        'answer_b_status': get_mode_status(question.ai_answer_b),
        'answer_c_status': get_mode_status(question.ai_answer_c),
        'answer_a': question.ai_answer_a,
        'answer_b': question.ai_answer_b,
        'answer_c': question.ai_answer_c,
    }
