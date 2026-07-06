"""API views for manual question creation."""
import logging
import uuid
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.parser.models import ExamQuestion, QuestionOption
from apps.papers.models import ExamPaper
from apps.common.codegen import generate_question_system_id

logger = logging.getLogger(__name__)


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_question(request):
    """Create a new question manually (not from paper parsing)."""
    data = request.data

    # Validate required fields
    paper_id = data.get('paper_id')
    if not paper_id:
        return Response({
            'code': 400, 'message': '必须指定所属试卷', 'data': None, 'trace_id': make_trace_id()
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        paper = ExamPaper.objects.get(id=paper_id, is_deleted=False)
    except ExamPaper.DoesNotExist:
        return Response({
            'code': 404, 'message': '试卷不存在', 'data': None, 'trace_id': make_trace_id()
        }, status=status.HTTP_404_NOT_FOUND)

    # Generate system_id using paper's subject
    subject = paper.subject or ''
    system_id = generate_question_system_id(subject)

    # Generate paper_question_no
    section_no = str(data.get('section_no', '1'))
    question_no = str(data.get('question_no', '1'))
    paper_question_no = f"{paper.paper_code}-{section_no}-{question_no}"

    question = ExamQuestion.objects.create(
        paper=paper,
        system_id=system_id,
        paper_question_no=paper_question_no,
        question_no=question_no,
        question_type=data.get('question_type', 'short_answer'),
        section_title=data.get('section_title', ''),
        stem=data.get('stem', ''),
        answer=data.get('answer', ''),
        analysis=data.get('analysis', ''),
        solution=data.get('solution', ''),
        knowledge_points=data.get('knowledge_points', []),
        difficulty=data.get('difficulty', 3),
        page_start=0,
        page_end=0,
        confidence=1.0,
        need_review=False,
        review_status='confirmed',
        parse_status='manual_created',
    )

    # Create options for choice-type questions
    qtype = data.get('question_type', '')
    if qtype in ('single_choice', 'multiple_choice'):
        options = data.get('options', [])
        for i, opt in enumerate(options):
            QuestionOption.objects.create(
                question=question,
                option_label=opt.get('label', chr(65 + i)),
                content=opt.get('content', ''),
                sort_order=i,
            )

    # Update paper total
    paper.total_questions = paper.questions.count()
    paper.save(update_fields=['total_questions'])

    return Response({
        'code': 0,
        'message': '题目创建成功',
        'data': {'question_id': question.id, 'system_id': system_id},
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_question_image(request):
    """Upload an image for a question."""
    from apps.common.oss_service import upload_crop_image_safe

    image_file = request.FILES.get('image')
    question_id = request.data.get('question_id')

    if not image_file:
        return Response({
            'code': 400, 'message': '缺少图片文件', 'data': None, 'trace_id': make_trace_id()
        }, status=status.HTTP_400_BAD_REQUEST)

    if not question_id:
        return Response({
            'code': 400, 'message': '缺少题目ID', 'data': None, 'trace_id': make_trace_id()
        }, status=status.HTTP_400_BAD_REQUEST)

    # Save uploaded file temporarily
    import tempfile
    import os
    suffix = os.path.splitext(image_file.name)[1] or '.jpg'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in image_file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        url = upload_crop_image_safe(tmp_path, f'questions/{question_id}/')
        if url is None:
            return Response({
                'code': 500, 'message': 'OSS上传失败：服务未配置', 'data': None, 'trace_id': make_trace_id()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'code': 0, 'message': '上传成功',
            'data': {'url': url},
            'trace_id': make_trace_id(),
        })
    except Exception as e:
        logger.error(f'Image upload failed: {e}')
        return Response({
            'code': 500, 'message': f'上传失败: {str(e)}', 'data': None, 'trace_id': make_trace_id()
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
