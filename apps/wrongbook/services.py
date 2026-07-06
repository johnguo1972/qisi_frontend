"""Wrong book services: variant question recommendation."""
from apps.parser.models import ExamQuestion


def find_variant_questions(question_id: int, limit: int = 3) -> list:
    """Find questions with same subject and difficulty as variant exercises."""
    try:
        original = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return []

    # Same subject + same difficulty + exclude original
    queryset = ExamQuestion.objects.filter(
        subject=original.subject,
    ).exclude(pk=question_id)

    # Filter by same difficulty if available
    if original.difficulty is not None:
        queryset = queryset.filter(difficulty=original.difficulty)

    variants = queryset[:limit]

    return [{
        'id': q.id,
        'question_no': q.question_no,
        'question_type': q.question_type,
        'difficulty': float(q.difficulty) if q.difficulty else None,
    } for q in variants]
