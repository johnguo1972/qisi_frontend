"""Import batch views: upload Word/PDF and start parsing."""
import os
import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from apps.papers.models import ExamPaper, ParseTask
from apps.parser.tasks import parse_paper_task
from .serializers import ImportBatchSerializer, PaperListSerializer


def make_trace_id():
    return uuid.uuid4().hex[:16]


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def import_batch_list(request):
    """Q-01/Q-02: Upload (POST) or list import batches (GET)."""
    if request.method == 'POST':
        return _handle_upload(request)
    return _handle_list(request)


def _handle_upload(request):
    """Q-01: Upload Word/PDF and start async parsing."""
    file = request.FILES.get('file')
    if not file:
        return Response(
            {'code': 4001, 'message': '请上传文件', 'data': None, 'trace_id': make_trace_id()},
            status=400
        )

    # Validate file extension
    name = file.name.lower()
    if not (name.endswith('.docx') or name.endswith('.doc') or name.endswith('.pdf')):
        return Response(
            {'code': 4002, 'message': '仅支持 .docx、.doc 或 .pdf 文件', 'data': None, 'trace_id': make_trace_id()},
            status=400
        )

    # Read all file chunks first (for saving and potential hash-based dedup in future)
    file_chunks = []
    for chunk in file.chunks():
        file_chunks.append(chunk)

    # Check if a paper with same filename (without extension) already exists
    title_base = file.name.rsplit('.', 1)[0]
    existing_paper = ExamPaper.objects.filter(
        title=title_base,
        is_deleted=False,
    ).first()

    if existing_paper:
        # Check who uploaded it
        uploader_name = '未知'
        if existing_paper.uploaded_by:
            uploader_name = existing_paper.uploaded_by.display_name or existing_paper.uploaded_by.mobile or '未知'
        return Response({
            'code': 409,
            'message': f'该试卷已存在，由用户"{uploader_name}"于{existing_paper.created_at.strftime("%Y-%m-%d %H:%M")}上传，无需重复上传',
            'data': {
                'paper_id': existing_paper.id,
                'paper_code': existing_paper.paper_code,
                'status': existing_paper.status,
                'uploaded_by': uploader_name,
                'created_at': existing_paper.created_at.isoformat(),
            },
            'trace_id': make_trace_id(),
        }, status=409)

    # Save uploaded file to media/uploads
    media_dir = settings.MEDIA_ROOT / 'uploads'
    os.makedirs(media_dir, exist_ok=True)
    file_path = str(media_dir / file.name)
    with open(file_path, 'wb+') as f:
        for chunk in file_chunks:
            f.write(chunk)

    # Derive subject/grade from filename or query params if provided
    subject = request.POST.get('subject', 'math')
    grade = request.POST.get('grade', '')
    title = request.POST.get('title', title_base)

    # Create ExamPaper record
    paper = ExamPaper.objects.create(
        title=title,
        subject=subject,
        grade=grade,
        source_file_path=f'uploads/{file.name}',
        status='uploaded',
        uploaded_by=request.user,
    )

    # Create ParseTask record
    task = ParseTask.objects.create(
        paper=paper,
        task_type='full_parse',
        status='running',
        progress=0,
        current_step='等待解析',
    )

    # Start async Celery task (or sync if ALWAYS_EAGER)
    if settings.CELERY_TASK_ALWAYS_EAGER:
        # Run synchronously — no Celery worker needed
        parse_paper_task(paper_id=paper.id)
        celery_task_id = None
    else:
        celery_result = parse_paper_task.delay(paper_id=paper.id)
        celery_task_id = celery_result.id

    task.celery_task_id = celery_task_id
    task.save(update_fields=['celery_task_id'])

    return Response({
        'code': 0,
        'message': '上传成功，解析中',
        'data': {
            'paper_id': paper.id,
            'task_id': task.id,
            'celery_task_id': celery_result.id,
        },
        'trace_id': make_trace_id(),
    })


def _handle_list(request):
    """Q-02: List import batches (only current user's uploads, excluding deleted)."""
    qs = ParseTask.objects.select_related('paper').filter(
        paper__uploaded_by=request.user,
        paper__is_deleted=False,
    ).order_by('-created_at')

    # Optional filters
    status = request.GET.get('status')
    if status:
        qs = qs.filter(status=status)

    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    page_size = min(page_size, 100)

    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size

    items = qs[start:end]
    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'items': ImportBatchSerializer(items, many=True).data,
            'total': total,
            'page_no': page,
            'page_size': page_size,
        },
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_batch_detail(request, batch_id):
    """Q-03: Import batch detail."""
    try:
        batch = ParseTask.objects.select_related('paper').get(pk=batch_id)
        return Response({
            'code': 0, 'message': 'success',
            'data': ImportBatchSerializer(batch).data,
            'trace_id': make_trace_id(),
        })
    except ParseTask.DoesNotExist:
        return Response(
            {'code': 404, 'message': '批次不存在', 'data': None, 'trace_id': make_trace_id()},
            status=404
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def paper_list(request):
    """List exam papers (import sources)."""
    qs = ExamPaper.objects.filter(is_deleted=False).order_by('-created_at')

    subject = request.GET.get('subject')
    if subject:
        qs = qs.filter(subject=subject)

    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    page_size = min(page_size, 100)

    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size

    items = qs[start:end]
    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'items': PaperListSerializer(items, many=True).data,
            'total': total,
            'page_no': page,
            'page_size': page_size,
        },
        'trace_id': make_trace_id(),
    })
