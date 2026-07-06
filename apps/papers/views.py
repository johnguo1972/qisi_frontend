"""Papers app views."""
import os
import uuid
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import ExamPaper, ParseTask
from apps.common import status as const
from apps.parser.tasks import parse_paper_task


@csrf_exempt
@require_http_methods(['POST'])
def upload_paper(request):
    """Upload a Word exam paper and create a parse task."""
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'No file provided'}, status=400)

    if not file.name.endswith('.docx'):
        return JsonResponse({'error': 'Only .docx files are accepted'}, status=400)

    title = (request.POST.get('title') or '').strip() or file.name
    subject = request.POST.get('subject', '数学')
    stage = request.POST.get('stage')
    grade = request.POST.get('grade')
    paper_type = request.POST.get('paper_type')
    has_solution = request.POST.get('has_solution', 'false').lower() == 'true'
    region = (request.POST.get('region') or '').strip()

    # Create paper record
    paper_id = str(uuid.uuid4())[:8]
    paper_dir = os.path.join(settings.MEDIA_ROOT, 'exams', paper_id, 'source')
    os.makedirs(paper_dir, exist_ok=True)
    file_path = os.path.join(paper_dir, file.name)

    with open(file_path, 'wb+') as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    paper = ExamPaper.objects.create(
        title=title,
        subject=subject,
        stage=stage,
        grade=grade,
        region=region,
        paper_type=paper_type,
        has_solution=has_solution,
        source_file_path=os.path.relpath(file_path, settings.MEDIA_ROOT),
        status=const.PAPER_UPLOADED,
        uploaded_by=getattr(request, 'user', None),
    )

    task = ParseTask.objects.create(
        paper=paper,
        task_type='full_parse',
        status=const.TASK_PENDING,
    )

    return JsonResponse({
        'paper_id': paper.id,
        'task_id': task.id,
        'status': const.PAPER_UPLOADED,
    }, status=201)


@csrf_exempt
@require_http_methods(['POST'])
def start_parse(request, paper_id):
    """Start parsing an exam paper."""
    try:
        paper = ExamPaper.objects.get(id=paper_id, is_deleted=False)
    except ExamPaper.DoesNotExist:
        return JsonResponse({'error': 'Paper not found'}, status=404)

    task = ParseTask.objects.create(
        paper=paper,
        task_type='full_parse',
        status=const.TASK_PENDING,
    )

    # Dispatch Celery task
    parse_paper_task.delay(paper.id)

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from celery import current_app


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_parse(request, paper_id):
    """Stop a running parse task."""
    paper = ExamPaper.objects.filter(id=paper_id, is_deleted=False).first()
    if not paper:
        return Response({
            'code': 404, 'message': '试卷不存在', 'data': None, 'trace_id': make_trace_id()
        }, status=404)

    task = ParseTask.objects.filter(paper=paper, status=const.TASK_RUNNING).first()
    if not task:
        return Response({
            'code': 400, 'message': '没有正在运行的解析任务', 'data': None, 'trace_id': make_trace_id()
        }, status=400)

    if task.celery_task_id:
        current_app.control.revoke(task.celery_task_id, terminate=True)

    task.status = const.TASK_FAILED
    task.error_message = '用户手动停止'
    task.finished_at = timezone.now()
    task.save()

    paper.status = const.PAPER_UPLOADED
    paper.save(update_fields=['status'])

    return Response({
        'code': 0, 'message': '已停止解析', 'data': None, 'trace_id': make_trace_id()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reparse_paper(request, paper_id):
    """Restart full parse for a paper."""
    paper = ExamPaper.objects.filter(id=paper_id, is_deleted=False).first()
    if not paper:
        return Response({
            'code': 404, 'message': '试卷不存在', 'data': None, 'trace_id': make_trace_id()
        }, status=404)

    running_task = ParseTask.objects.filter(paper=paper, status=const.TASK_RUNNING).first()
    if running_task:
        return Response({
            'code': 400, 'message': '已有解析任务正在运行', 'data': None, 'trace_id': make_trace_id()
        }, status=400)

    result = parse_paper_task.delay(paper.id)

    task = ParseTask.objects.create(
        paper=paper, task_type='full_parse', status=const.TASK_RUNNING,
        celery_task_id=str(result.id)
    )

    paper.status = const.PAPER_PARSING
    paper.save(update_fields=['status'])

    return Response({
        'code': 0, 'message': '已重新开始解析',
        'data': {'paper_id': paper.id, 'task_id': task.id, 'celery_task_id': str(result.id)},
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def paper_parse_progress(request, paper_id):
    """Get parse progress for a paper."""
    paper = ExamPaper.objects.filter(id=paper_id, is_deleted=False).first()
    if not paper:
        return Response({
            'code': 404, 'message': '试卷不存在', 'data': None, 'trace_id': make_trace_id()
        }, status=404)

    task = ParseTask.objects.filter(paper=paper).order_by('-created_at').first()
    if not task:
        return Response({
            'code': 404, 'message': '没有解析任务', 'data': None, 'trace_id': make_trace_id()
        }, status=404)

    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'paper_id': paper.id,
            'paper_code': paper.paper_code,
            'status': paper.status,
            'task_status': task.status,
            'progress': task.progress,
            'current_step': task.current_step,
            'total_questions': paper.total_questions,
        },
        'trace_id': make_trace_id(),
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_paper(request, paper_id):
    """Soft delete an exam paper."""
    paper = ExamPaper.objects.filter(id=paper_id, is_deleted=False).first()
    if not paper:
        return Response({
            'code': 404, 'message': '试卷不存在', 'data': None, 'trace_id': make_trace_id()
        }, status=404)

    # Check if paper is currently being parsed
    running_task = ParseTask.objects.filter(paper=paper, status=const.TASK_RUNNING).first()
    if running_task:
        return Response({
            'code': 400, 'message': '试卷正在解析中，请先停止解析', 'data': None, 'trace_id': make_trace_id()
        }, status=400)

    # Soft delete
    paper.is_deleted = True
    paper.save(update_fields=['is_deleted'])

    # Also mark related parse tasks as cancelled
    ParseTask.objects.filter(paper=paper).update(status=const.TASK_CANCELLED)

    return Response({
        'code': 0, 'message': '试卷已删除', 'data': None, 'trace_id': make_trace_id()
    })
