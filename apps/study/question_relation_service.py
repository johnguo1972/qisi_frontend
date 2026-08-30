"""Helpers for normalizing question pairs and finding relation candidates."""

from decimal import Decimal


MISSING_CANDIDATE_METADATA_REASON = '当前题目缺少学科、难度或知识点，无法生成可关联题'


def canonical_question_pair(question_a, question_b):
    """Return a pair in stable UUID order so one relation has one database row."""
    if str(question_a.pk) <= str(question_b.pk):
        return question_a, question_b
    return question_b, question_a


def knowledge_point_keys(raw_points):
    """Normalize legacy and structured knowledge points into comparable keys."""
    if isinstance(raw_points, dict):
        raw_points = raw_points.get('points') or raw_points.get('knowledge_points') or [raw_points]
    elif isinstance(raw_points, str):
        raw_points = [raw_points]

    if not isinstance(raw_points, (list, tuple, set)):
        return set()

    keys = set()
    for point in raw_points:
        if isinstance(point, dict):
            for field in ('id', 'module', 'name'):
                value = point.get(field)
                if value is not None and str(value).strip():
                    keys.add(f'{field}:{str(value).strip()}')
                    break
        elif isinstance(point, str) and point.strip():
            keys.add(f'name:{point.strip()}')
    return keys


def find_relation_candidates(question, visible_questions):
    """Return visible, unlinked questions matching subject, difficulty and knowledge."""
    origin_keys = knowledge_point_keys(question.knowledge_points)
    if not question.subject or question.difficulty is None or not origin_keys:
        return [], MISSING_CANDIDATE_METADATA_REASON

    from .models import QuestionRelation

    related_ids = {
        question_id
        for pair in QuestionRelation.for_question(question).values_list(
            'question_left_id', 'question_right_id'
        )
        for question_id in pair
        if question_id != question.pk
    }
    difficulty = Decimal(str(question.difficulty))
    candidates = visible_questions.filter(
        subject=question.subject,
        difficulty__gte=difficulty - Decimal('0.5'),
        difficulty__lte=difficulty + Decimal('0.5'),
    ).exclude(pk=question.pk).exclude(pk__in=related_ids)

    return [
        candidate
        for candidate in candidates
        if knowledge_point_keys(candidate.knowledge_points) & origin_keys
    ], None
