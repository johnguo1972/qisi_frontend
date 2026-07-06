"""Wrong book API views: S-09/S-10/S-11 + mastery records."""
import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import WrongBookItem, MasteryRecord
from .serializers import WrongBookItemSerializer, WrongBookDetailSerializer, MasteryRecordSerializer
from .services import find_variant_questions


def make_trace_id():
    return uuid.uuid4().hex[:16]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wrongbook_list(request):
    """S-09: Wrong book list."""
    status_filter = request.GET.get('status')
    qs = WrongBookItem.objects.filter(student_user_id=request.user)
    if status_filter:
        qs = qs.filter(status=status_filter)
    qs = qs.order_by('-latest_wrong_at')

    return Response({
        'code': 0, 'message': 'success',
        'data': WrongBookItemSerializer(qs, many=True).data,
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wrongbook_detail(request, item_id):
    """S-10: Wrong book item detail."""
    try:
        item = WrongBookItem.objects.get(pk=item_id, student_user_id=request.user)
    except WrongBookItem.DoesNotExist:
        return Response({
            'code': 404, 'message': '错题不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)

    return Response({
        'code': 0, 'message': 'success',
        'data': WrongBookDetailSerializer(item).data,
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wrongbook_variants(request, item_id):
    """S-11: Find variant questions for practice."""
    try:
        item = WrongBookItem.objects.get(pk=item_id, student_user_id=request.user)
    except WrongBookItem.DoesNotExist:
        return Response({
            'code': 404, 'message': '错题不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)

    variants = find_variant_questions(item.question_id, limit=3)
    return Response({
        'code': 0, 'message': 'success',
        'data': variants,
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mastery_list(request):
    """List mastery records for the current student."""
    records = MasteryRecord.objects.filter(
        student_user_id=request.user
    ).order_by('-updated_at')
    return Response({
        'code': 0, 'message': 'success',
        'data': MasteryRecordSerializer(records, many=True).data,
        'trace_id': make_trace_id(),
    })
