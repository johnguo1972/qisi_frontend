"""Wrong book services: variant question recommendation."""
from apps.parser.models import ExamQuestion


def _question_brief(q):
    """组装一道题的完整展示数据（含选项/图片）。"""
    return {
        'id': q.id,
        'question_no': q.question_no,
        'question_type': q.question_type,
        'subject': q.subject,
        'difficulty': float(q.difficulty) if q.difficulty else None,
        'stem': q.stem,
        'stem_html': getattr(q, 'stem_html', None),
        'images': [{'url': img.file_path} for img in q.images.all().order_by('sort_order')],
        'options': [{'label': o.option_label, 'content': o.content}
                    for o in q.options.all().order_by('sort_order')],
    }


def find_variant_questions(question_id: int, limit: int = 3) -> list:
    """同学科 + 同难度（可空）+ 排除原题，返回完整题目数据。
    过滤掉没有选项的选择题（数据不完整）。
    """
    try:
        original = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return []

    qs = ExamQuestion.objects.filter(subject=original.subject).exclude(pk=question_id)
    if original.difficulty is not None:
        qs = qs.filter(difficulty=original.difficulty)
    qs = qs.prefetch_related('images', 'options')

    results = []
    for q in qs:
        brief = _question_brief(q)
        choice_types = ('single_choice', 'multiple_choice')
        if q.question_type in choice_types and not brief['options']:
            continue
        results.append(brief)
        if len(results) >= limit:
            break
    return results
