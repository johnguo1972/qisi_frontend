"""Question search/detail/update/publish views."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, CharField
from django.db.models.functions import Cast
from apps.parser.models import ExamQuestion
from apps.knowledge.models import KnowledgePoint
from .serializers import QuestionListSerializer, QuestionDetailSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_list(request):
    """Q-05: Question search/list with filters."""
    subject = request.GET.get('subject')
    difficulty = request.GET.get('difficulty')
    question_type = request.GET.get('question_type')
    tag = request.GET.get('tag', '').strip()
    question_uuid = request.GET.get('uuid', '').strip()
    knowledge = request.GET.get('knowledge')
    question_no = request.GET.get('question_no')
    review_status = request.GET.get('review_status')
    paper_id = request.GET.get('paper_id')
    knowledge_point_id = request.GET.get('knowledge_point_id', '')
    stages = request.GET.get('stages', '')

    qs = ExamQuestion.objects.select_related('paper').all()

    if review_status:
        qs = qs.filter(review_status=review_status)
    if subject:
        qs = qs.filter(subject=subject)
    if difficulty:
        diff_values = [value.strip() for value in difficulty.split(',') if value.strip()]
        try:
            diff_values = [float(value) for value in diff_values]
            if len(diff_values) == 1:
                qs = qs.filter(difficulty=diff_values[0])
            elif diff_values:
                qs = qs.filter(difficulty__in=diff_values)
        except (ValueError, TypeError):
            pass
    if question_type:
        qs = qs.filter(question_type=question_type)
    if tag:
        qs = qs.filter(tags__contains=[tag])
    if question_uuid:
        # UUID 字段不能直接使用字符串 icontains；转换为文本后支持输入完整 UUID
        # 或任意片段的模糊查询，例如前 8 位、后 6 位等。
        qs = qs.annotate(uuid_text=Cast('id', output_field=CharField())).filter(
            uuid_text__icontains=question_uuid
        )
    if question_no:
        qs = qs.filter(
            Q(question_no__icontains=question_no) |
            Q(paper_question_no__icontains=question_no) |
            Q(system_id__icontains=question_no)
        )
    if paper_id:
        try:
            qs = qs.filter(paper_id=int(paper_id))
        except (ValueError, TypeError):
            pass
    if knowledge:
        qs = qs.filter(ai_knowledge_enrichment__contains=[{'code': knowledge}])

    if stages:
        stage_query = Q()
        for value in stages.split(','):
            # The teacher page displays a combined grade/term label while
            # imported papers store grade/stage separately.
            for part in value.strip().split():
                if part:
                    stage_query |= Q(paper__grade__icontains=part) | Q(paper__stage__icontains=part)
        if stage_query:
            qs = qs.filter(stage_query)

    # Filter by the manually associated knowledge point first.  The older
    # AI-enrichment fallback is retained for questions that only have AI data.
    if knowledge_point_id:
        kp_values = [value.strip() for value in knowledge_point_id.split(',') if value.strip()]
        if '-1' in kp_values:
            qs = qs.filter(Q(knowledge_points__isnull=True) | Q(knowledge_points=[]))
        else:
            kp_query = Q()
            for value in kp_values:
                try:
                    kp_id = int(value)
                    kp_query |= (
                        Q(knowledge_points__contains=[{'id': kp_id}]) |
                        Q(knowledge_points__contains=[{'id': str(kp_id)}]) |
                        Q(ai_knowledge_enrichment__contains=[{'id': kp_id}])
                    )
                except (ValueError, TypeError):
                    try:
                        kp = KnowledgePoint.objects.get(pk=value)
                        kp_query |= Q(knowledge_points__contains=[{'module': kp.module}])
                    except (KnowledgePoint.DoesNotExist, ValueError, TypeError):
                        continue
            if kp_query:
                qs = qs.filter(kp_query)

    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    page_size = min(page_size, 100)  # cap

    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size

    items = qs.order_by('sort_order', 'id')[start:end]
    return Response({
        'code': 0, 'message': 'success', 'trace_id': '',
        'data': {
            'items': QuestionListSerializer(items, many=True).data,
            'total': total,
            'page_no': page,
            'page_size': page_size,
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def similar_questions(request, question_id):
    """Return questions with the same main knowledge point and similar difficulty."""
    try:
        question = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None}, status=404)

    raw_points = question.knowledge_points or []
    if isinstance(raw_points, dict):
        raw_points = raw_points.get('points', [])
    main_point = next((item for item in raw_points if isinstance(item, dict) and (item.get('module') or item.get('id'))), None)
    modules = [main_point.get('module')] if main_point and main_point.get('module') else []
    ids = [main_point.get('id')] if main_point and main_point.get('id') else []
    query = Q()
    for module in modules:
        query |= Q(knowledge_points__contains=[{'module': module}])
    for point_id in ids:
        query |= Q(knowledge_points__contains=[{'id': point_id}])

    candidates = ExamQuestion.objects.exclude(pk=question.pk).filter(subject=question.subject)
    if not modules and not ids:
        return Response({'code': 0, 'data': []})
    candidates = candidates.filter(query)
    if question.difficulty is not None:
        candidates = candidates.filter(
            difficulty__gte=max(0, float(question.difficulty) - 1),
            difficulty__lte=float(question.difficulty) + 1,
        )

    items = candidates.order_by('difficulty', 'sort_order')[:20]
    return Response({'code': 0, 'data': QuestionListSerializer(items, many=True).data})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def question_detail(request, question_id):
    """Q-07 / Q-08: Question detail / update."""
    try:
        q = ExamQuestion.objects.select_related('paper').get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response(
            {'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': ''},
            status=404
        )

    if request.method == 'GET':
        return Response({
            'code': 0, 'message': 'success',
            'data': QuestionDetailSerializer(q).data,
            'trace_id': ''
        })

    # PUT: update editable fields
    editable = ['ai_answer_a', 'ai_answer_b', 'ai_answer_c',
                'difficulty', 'subject', 'review_status',
                'stem', 'stem_html', 'answer', 'analysis', 'solution',
                'knowledge_points', 'tags', 'need_review', 'formula_need_review']
    for field in editable:
        if field in request.data:
            setattr(q, field, request.data[field])
    q.save()
    return Response({'code': 0, 'message': '更新成功', 'data': None, 'trace_id': ''})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_publish(request, question_id):
    """Q-09: Publish (confirm) a question."""
    try:
        q = ExamQuestion.objects.get(pk=question_id)
        q.review_status = 'confirmed'
        q.need_review = False
        q.save()
        return Response({'code': 0, 'message': '发布成功', 'data': None, 'trace_id': ''})
    except ExamQuestion.DoesNotExist:
        return Response(
            {'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': ''},
            status=404
        )
