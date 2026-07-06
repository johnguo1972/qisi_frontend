"""DRF views for review API."""
import json
import logging
from rest_framework import generics, status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from celery.result import AsyncResult
from django.core.cache import cache
from django.db.models.functions import Cast
from django.db.models import IntegerField, Case, When, Value, CharField, F
from apps.parser.models import ExamQuestion, ExamPage
from apps.papers.models import ExamPaper
from apps.common.batch_tasks import batch_ai_process_questions
from .serializers import (
    QuestionDetailSerializer, QuestionUpdateSerializer,
    QuestionListSerializer, PaperReviewSerializer
)
from .services.question_edit_service import update_question

logger = logging.getLogger(__name__)


@api_view(['GET'])
def paper_review_list(request):
    """List all papers available for review."""
    papers = ExamPaper.objects.filter(is_deleted=False).order_by('-created_at')
    serializer = PaperReviewSerializer(papers, many=True)
    return Response({'success': True, 'data': serializer.data})


@api_view(['GET'])
def question_list(request, paper_id):
    """List all questions for a given paper."""
    try:
        paper = ExamPaper.objects.get(id=paper_id, is_deleted=False)
    except ExamPaper.DoesNotExist:
        raise NotFound(f'Paper {paper_id} not found')

    questions = ExamQuestion.objects.filter(paper=paper).annotate(
        qno_int=Cast(
            # Only cast purely numeric question_no; non-numeric become NULL → sort last
            Case(
                When(question_no__regex=r'^\d+$', then='question_no'),
                default=Value(None, output_field=CharField()),
                output_field=CharField(),
            ),
            IntegerField(),
        )
    ).order_by(F('qno_int').asc(nulls_last=True))

    # Support status filtering via query param
    status_filter = request.query_params.get('status')
    if status_filter and status_filter != 'all':
        questions = questions.filter(review_status=status_filter)

    serializer = QuestionListSerializer(questions, many=True)
    return Response({'success': True, 'data': serializer.data, 'paper': {
        'id': paper.id, 'title': paper.title, 'status': paper.status
    }})


@api_view(['GET'])
def question_detail(request, question_id):
    """Get full detail of a single question."""
    try:
        question = ExamQuestion.objects.select_related('paper').prefetch_related(
            'options', 'images'
        ).get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')

    serializer = QuestionDetailSerializer(question)
    return Response({'success': True, 'data': serializer.data})


@api_view(['PATCH'])
def question_update(request, question_id):
    """Update a question during human review."""
    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')

    serializer = QuestionUpdateSerializer(question, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)

    # Collect option data from request (serializer doesn't handle options)
    option_data = {}
    for key in request.data:
        if key.startswith('option_') and len(key) == 8:
            option_data[key[7:]] = request.data[key]

    updated = update_question(question, serializer.validated_data, option_data)
    return Response({
        'success': True,
        'data': QuestionDetailSerializer(updated).data
    })


@api_view(['POST'])
def question_confirm(request, question_id):
    """Confirm a question as correct."""
    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')

    question.review_status = 'confirmed'
    question.need_review = False
    question.save()

    return Response({'success': True, 'message': 'Question confirmed'})


@api_view(['POST'])
def question_reject(request, question_id):
    """Mark a question for re-processing."""
    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')

    question.review_status = 'rejected'
    question.need_review = True
    question.parse_status = 'needs_reparse'
    question.save()

    return Response({'success': True, 'message': 'Question marked for re-processing'})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def question_delete(request, question_id):
    """Hard delete a question and its related images/options."""
    from apps.parser.models import QuestionImage, QuestionOption

    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None}, status=404)

    # Delete related images and options
    QuestionImage.objects.filter(question=question).delete()
    QuestionOption.objects.filter(question=question).delete()

    # Hard delete the question
    question.delete()

    return Response({'code': 0, 'message': '删除成功', 'data': None})


# ===== AI Review endpoints =====

from .services.ai_review_service import (
    process_single_question, confirm_ai_answer,
    update_ai_answer, update_knowledge_enrichment, get_ai_status,
)
from .serializers import AIStatusSerializer, AIProcessRequestSerializer


@api_view(['POST'])
def ai_process_question(request, question_id):
    """Start async AI processing (knowledge + A/B/C) for a single question via Celery."""
    try:
        ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')

    serializer = AIProcessRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    model = serializer.validated_data.get('model')

    from .tasks import single_ai_process_question
    task = single_ai_process_question.delay(question_id, model=model)

    return Response({
        'success': True,
        'data': {'task_id': task.id, 'status': 'pending'},
    })


@api_view(['GET'])
def single_ai_task_status(request, task_id):
    """Get async single AI task progress."""

    progress_data = cache.get(f'single_ai_progress:{task_id}')
    if not progress_data:
        # Check if Celery task exists (might be still pending)
        result = AsyncResult(task_id)
        if result.state in ('PENDING', 'STARTED'):
            return Response({
                'success': True,
                'data': {'status': 'pending', 'step': 'starting',
                         'step_label': '任务排队中...', 'result': None, 'error': None},
            })
        return Response({'success': False, 'error': 'Task not found'}, status=404)

    data = json.loads(progress_data)
    return Response({'success': True, 'data': data})


@api_view(['POST'])
def ai_process_single_mode(request, question_id, mode):
    """Start async AI processing for a single mode (A/B/C) via Celery."""
    mode = mode.upper()
    if mode not in ('A', 'B', 'C'):
        return Response({
            'code': 4001, 'message': f'不支持的模式: {mode}，仅支持 A/B/C', 'data': None, 'trace_id': make_trace_id()
        }, status=400)

    try:
        ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')

    serializer = AIProcessRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    model = serializer.validated_data.get('model')

    from .tasks import single_mode_ai_process_question
    task = single_mode_ai_process_question.delay(question_id, mode, model=model)

    return Response({
        'success': True,
        'data': {'task_id': task.id, 'status': 'pending', 'mode': mode},
    })


@api_view(['POST'])
def ai_confirm_answer(request, question_id, mode):
    """Confirm an AI answer for a given mode (A/B/C)."""
    try:
        result = confirm_ai_answer(question_id, mode)
        return Response({'success': True, 'data': result})
    except ValueError as e:
        return Response({'success': False, 'error': str(e)}, status=400)


@api_view(['PATCH', 'PUT'])
def ai_update_answer(request, question_id, mode):
    """Edit an AI answer content."""
    edited_content = request.data.get('edited_content')
    if not edited_content:
        return Response({'success': False, 'error': 'edited_content required'}, status=400)

    try:
        result = update_ai_answer(question_id, mode, edited_content)
        return Response({'success': True, 'data': result})
    except ValueError as e:
        return Response({'success': False, 'error': str(e)}, status=400)


@api_view(['POST'])
def ai_update_knowledge(request, question_id):
    """Edit knowledge enrichment data."""
    updated_data = request.data.get('knowledge_data')
    if not updated_data:
        return Response({'success': False, 'error': 'knowledge_data required'}, status=400)

    try:
        result = update_knowledge_enrichment(question_id, updated_data)
        return Response({'success': True, 'data': result})
    except ValueError as e:
        return Response({'success': False, 'error': str(e)}, status=400)


@api_view(['GET'])
def ai_question_status(request, question_id):
    """Get AI processing status for a question."""
    try:
        ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')

    data = get_ai_status(question_id)
    return Response({'success': True, 'data': data})


# ===== Batch AI processing endpoints =====


@api_view(['POST'])
def batch_ai_process(request):
    """Start batch AI processing for selected questions."""
    question_ids = request.data.get('question_ids', [])
    if not question_ids:
        return Response({'success': False, 'error': 'question_ids required'}, status=400)

    model = request.data.get('model')

    task = batch_ai_process_questions.delay(question_ids, model)

    return Response({
        'success': True,
        'data': {
            'task_id': task.id,
            'total': len(question_ids),
            'status': 'pending',
        }
    })


@api_view(['GET'])
def batch_task_status(request, task_id):
    """Get batch task progress."""
    progress_data = cache.get(f'batch_progress:{task_id}')
    if not progress_data:
        return Response({'success': False, 'error': 'Task not found'}, status=404)

    data = json.loads(progress_data)
    return Response({'success': True, 'data': data})


@api_view(['POST'])
def batch_task_cancel(request, task_id):
    """Cancel a running batch task."""
    cache.set(f'batch_cancel:{task_id}', '1', timeout=60)
    return Response({'success': True, 'message': 'Cancel requested'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_question_assets(request, question_id):
    """获取原图列表(ExamPage)和已截插图列表(QuestionImage)"""
    from apps.parser.models import QuestionImage
    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')
        
    pages = ExamPage.objects.filter(paper=question.paper).order_by('page_no')
    images = QuestionImage.objects.filter(question=question).exclude(image_type='source').order_by('sort_order')
    
    pages_data = [{'page_no': p.page_no, 'image_path': p.image_path, 'width': p.width, 'height': p.height} for p in pages]
    from .serializers import QuestionImageListSerializer
    images_serializer = QuestionImageListSerializer(images, many=True)
    return Response({
        'code': 0,
        'data': {
            'pages': pages_data,
            'images': images_serializer.data
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def crop_question_image_api(request, question_id):
    """保存手工截图插图"""
    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')
        
    try:
        x1 = int(request.data.get('x1', 0))
        y1 = int(request.data.get('y1', 0))
        x2 = int(request.data.get('x2', 0))
        y2 = int(request.data.get('y2', 0))
        page_no = int(request.data.get('page_no', 1))
    except (ValueError, TypeError):
        return Response({'code': 400, 'message': 'Invalid coordinate values'}, status=400)
    description = request.data.get('description', '人工裁剪').strip()
    
    if x2 <= x1 or y2 <= y1:
        return Response({'code': 400, 'message': '坐标边界无效'}, status=400)
        
    from apps.review.services.image_recrop_service import recrop_question_image
    img = recrop_question_image(
        question, 
        [x1, y1, x2, y2], 
        page_no=page_no, 
        description=description
    )
    from .serializers import QuestionImageListSerializer
    return Response({'code': 0, 'data': QuestionImageListSerializer(img).data})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_question_image_api(request, question_id, image_id):
    """删除裁剪插图"""
    from apps.parser.models import QuestionImage
    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise NotFound(f'Question {question_id} not found')
        
    try:
        img = QuestionImage.objects.get(id=image_id, question=question)
        from apps.review.services.image_recrop_service import delete_question_image
        delete_question_image(img)
        return Response({'code': 0, 'message': '删除成功'})
    except QuestionImage.DoesNotExist:
        return Response({'code': 404, 'message': '插图不存在'}, status=404)


@api_view(['GET'])
def ai_task_status(request, task_id):
    """Get AI task progress status."""

    progress_data = cache.get(f'single_ai_progress:{task_id}')
    if not progress_data:
        return Response({
            'success': True,
            'data': {'status': 'pending', 'step': 'starting',
                     'step_label': '任务排队中...', 'result': None, 'error': None},
        })

    data = json.loads(progress_data)
    return Response({'success': True, 'data': data})
