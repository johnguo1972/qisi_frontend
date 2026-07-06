"""Question search/detail/update/publish views."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from apps.parser.models import ExamQuestion
from .serializers import QuestionListSerializer, QuestionDetailSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_list(request):
    """Q-05: Question search/list with filters."""
    subject = request.GET.get('subject')
    difficulty = request.GET.get('difficulty')
    knowledge = request.GET.get('knowledge')
    question_no = request.GET.get('question_no')
    review_status = request.GET.get('review_status')
    paper_id = request.GET.get('paper_id')
    knowledge_point_id = request.GET.get('knowledge_point_id', '')

    qs = ExamQuestion.objects.select_related('paper').all()

    if review_status:
        qs = qs.filter(review_status=review_status)
    if subject:
        qs = qs.filter(subject=subject)
    if difficulty:
        try:
            diff_val = float(difficulty)
            qs = qs.filter(difficulty=diff_val)
        except (ValueError, TypeError):
            pass
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

    # Filter by knowledge point ID (JSONField containment)
    if knowledge_point_id:
        try:
            kp_id = int(knowledge_point_id)
            qs = qs.filter(ai_knowledge_enrichment__contains=[{'id': kp_id}])
        except (ValueError, TypeError):
            pass

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
                'knowledge_points', 'need_review', 'formula_need_review']
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
