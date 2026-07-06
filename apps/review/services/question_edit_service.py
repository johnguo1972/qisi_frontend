"""Question editing for human review."""
import logging
from apps.common import status as const
from apps.parser.models import QuestionOption

logger = logging.getLogger(__name__)


def update_question(question, data: dict, option_data: dict = None):
    """Update question fields based on human review data.

    Args:
        question: ExamQuestion instance
        data: validated serializer data for question-level fields
        option_data: optional dict of {label: content} e.g. {'A': '...', 'D': '...'}
    """
    updatable = [
        'stem', 'stem_html', 'answer', 'analysis', 'solution',
        'comment', 'raw_explanation', 'knowledge_points', 'difficulty',
        'question_type', 'review_status', 'page_start', 'page_end',
    ]
    for field in updatable:
        if field in data:
            setattr(question, field, data[field])

    if data.get('review_status') == const.QUESTION_CONFIRMED:
        question.need_review = False
        question.parse_status = const.QUESTION_CONFIRMED
    elif data.get('review_status') == const.QUESTION_MODIFIED:
        question.need_review = False
        question.parse_status = const.QUESTION_MODIFIED

    question.save()

    # Update option contents if provided
    if option_data:
        for label, content in option_data.items():
            QuestionOption.objects.update_or_create(
                question=question,
                option_label=label,
                defaults={'content': content},
            )

    return question
