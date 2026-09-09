"""Background preparation for student guidance content."""

from __future__ import annotations

from celery import shared_task

from apps.common.ai.components import GuidanceComponent, QuestionInput
from apps.parser.models import ExamQuestion


@shared_task(
    bind=True,
    name='apps.study.tasks.prepare_guidance_content',
    max_retries=0,
)
def prepare_guidance_content(self, question_id: str):
    """Prepare missing C-mode steps without blocking a student request."""
    try:
        question = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return {'status': 'question_missing', 'question_id': str(question_id)}

    if isinstance(question.ai_answer_c, dict) and question.ai_answer_c.get('questions'):
        return {'status': 'already_prepared', 'question_id': str(question_id)}

    generated = GuidanceComponent().generate(
        QuestionInput(stem=question.stem or '', answer=question.answer or '')
    )
    steps = (generated or {}).get('steps') or []
    if not steps:
        return {'status': 'empty', 'question_id': str(question_id)}

    # Persist only the existing C-mode contract. Provider-added fields are not
    # copied into the question or session log.
    questions = [
        {
            'question': str(step.get('question') or '').strip(),
            'reference_answer': str(step.get('hint') or '').strip(),
            'key_points': [],
        }
        for step in steps
        if str(step.get('question') or '').strip()
    ]
    if not questions:
        return {'status': 'empty', 'question_id': str(question_id)}

    question.ai_answer_c = {
        'questions': questions,
        'summary': (generated or {}).get('summary', ''),
        'final_answer': (generated or {}).get('final_answer', ''),
    }
    question.save(update_fields=['ai_answer_c', 'updated_at'])
    return {
        'status': 'prepared',
        'question_id': str(question_id),
        'total_steps': len(questions),
    }
