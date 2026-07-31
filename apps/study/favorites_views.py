"""Teacher favorites API views."""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from apps.parser.models import ExamQuestion
from apps.study.models import Favorite
from apps.knowledge.models import KnowledgePoint
from django.db.models import Q

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def favorites_list(request):
    """List current user's favorited questions with filters."""
    question_type = request.GET.get('question_type', '')
    knowledge_point_id = request.GET.get('knowledge_point_id', '')
    search = request.GET.get('search', '')
    subject = request.GET.get('subject', '')

    fav_ids = Favorite.objects.filter(
        user=request.user
    ).values_list('question_id', flat=True)

    qs = ExamQuestion.objects.select_related('paper').filter(
        id__in=fav_ids
    )
    subject_map = {'数学': 'math', '物理': 'physics', '化学': 'chemistry', '英语': 'english', '语文': 'chinese'}
    if subject:
        db_subject = subject_map.get(subject, subject)
        qs = qs.filter(Q(subject=db_subject) | Q(subject=subject))

    if question_type:
        qs = qs.filter(question_type=question_type)
    if search:
        qs = qs.filter(stem__icontains=search)
    if knowledge_point_id:
        if knowledge_point_id == '-1':
            qs = qs.filter(Q(knowledge_points__isnull=True) | Q(knowledge_points=[]))
        else:
            try:
                kp_id = int(knowledge_point_id)
                qs = qs.filter(knowledge_points__contains=[{'id': kp_id}])
            except (ValueError, TypeError):
                try:
                    kp = KnowledgePoint.objects.get(pk=knowledge_point_id)
                    qs = qs.filter(knowledge_points__contains=[{'module': kp.module}])
                except (KnowledgePoint.DoesNotExist, ValueError, TypeError):
                    pass

    qs = qs.order_by('-created_at')

    items = []
    for q in qs:
        kp_count = 0
        if q.ai_knowledge_enrichment:
            kp_count = len(q.ai_knowledge_enrichment.get('points', q.ai_knowledge_enrichment))
        elif q.knowledge_points:
            kp_count = len(q.knowledge_points) if isinstance(q.knowledge_points, list) else 0

        items.append({
            'id': q.id,
            'favorite_id': None,  # not needed for remove (we use question_id)
            'question_id': q.id,
            'question_no': q.system_id or q.question_no,
            'paper_title': q.paper.title if q.paper else '',
            'difficulty': float(q.difficulty) if q.difficulty else None,
            'question_type': q.question_type,
            'question_type_text': q.get_question_type_display_label(),
            'knowledge_points_count': kp_count,
            'stem_preview': (q.stem[:80] + '...') if q.stem and len(q.stem) > 80 else (q.stem or ''),
            'created_at': q.created_at.isoformat() if q.created_at else '',
        })

    return Response({
        'code': 0, 'message': 'success', 'trace_id': '',
        'data': items,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def favorites_add(request):
    """Add a question to favorites."""
    question_id = request.data.get('question_id')
    if not question_id:
        return Response({
            'code': 400, 'message': 'question_id required', 'trace_id': '',
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check if question exists
    if not ExamQuestion.objects.filter(id=question_id).exists():
        return Response({
            'code': 404, 'message': '题目不存在', 'trace_id': '',
        }, status=status.HTTP_404_NOT_FOUND)

    # Check if already favorited
    if Favorite.objects.filter(user=request.user, question_id=question_id).exists():
        return Response({
            'code': 409, 'message': '已在精选中', 'trace_id': '',
        }, status=status.HTTP_409_CONFLICT)

    fav = Favorite.objects.create(user=request.user, question_id=question_id)
    return Response({
        'code': 0, 'message': '已加入精选', 'data': {'id': fav.id}, 'trace_id': '',
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def favorites_remove(request, question_id):
    """Remove a question from favorites by question_id."""
    deleted, _ = Favorite.objects.filter(
        user=request.user, question_id=question_id
    ).delete()

    if deleted == 0:
        return Response({
            'code': 404, 'message': '精选记录不存在', 'trace_id': '',
        }, status=status.HTTP_404_NOT_FOUND)

    return Response({
        'code': 0, 'message': '已移除', 'trace_id': '',
    })
