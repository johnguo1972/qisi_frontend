"""Papers app views."""
import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common import status as const

from .models import ExamPaper, ParseTask


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_paper(request, paper_id):
    """Soft delete an exam paper."""
    paper = ExamPaper.objects.filter(id=paper_id, is_deleted=False).first()
    if not paper:
        return Response({
            'code': 404, 'message': '试卷不存在', 'data': None, 'trace_id': make_trace_id()
        }, status=404)

    # Soft delete
    paper.is_deleted = True
    paper.save(update_fields=['is_deleted'])

    # Also mark related parse tasks as cancelled
    ParseTask.objects.filter(paper=paper).update(status=const.TASK_CANCELLED)

    return Response({
        'code': 0, 'message': '试卷已删除', 'data': None, 'trace_id': make_trace_id()
    })
