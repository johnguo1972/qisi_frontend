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
    """按知识点匹配变式题（优先于学科+难度）。

    优先匹配原题的知识点，知识点匹配不足时再按学科+难度补充。
    """
    try:
        original = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return []

    # 获取原题知识点
    original_kps = original.knowledge_points or []
    kp_modules = [kp.get('module') for kp in original_kps if isinstance(kp, dict) and kp.get('module')]

    qs = ExamQuestion.objects.exclude(pk=question_id)

    if kp_modules:
        # 优先匹配知识点：JSONField 的 __contains 查询数组元素
        from django.db.models import Q
        kp_query = Q()
        for module in kp_modules:
            kp_query |= Q(knowledge_points__contains=[{'module': module}])
        matched = qs.filter(kp_query).prefetch_related('images', 'options')
        matched_count = matched.count()
        if matched_count >= limit:
            results = matched[:limit]
        else:
            # 知识点匹配不足时，补充同科目+同难度
            remainder = limit - matched_count
            remainder_qs = qs.exclude(id__in=list(matched.values_list('id', flat=True)))
            if original.difficulty is not None:
                remainder_qs = remainder_qs.filter(
                    subject=original.subject,
                    difficulty=original.difficulty
                )
            else:
                remainder_qs = remainder_qs.filter(subject=original.subject)
            results = list(matched) + list(remainder_qs[:remainder])
    else:
        # 原题无知识点，按学科+难度匹配（当前逻辑）
        if original.difficulty is not None:
            qs = qs.filter(subject=original.subject, difficulty=original.difficulty)
        else:
            qs = qs.filter(subject=original.subject)
        results = qs.prefetch_related('images', 'options')[:limit]

    return [_question_brief(q) for q in results]
