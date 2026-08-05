"""API views for photo-based question creation."""
import logging
import os
import json
import time
import uuid
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.parser.models import ExamQuestion, QuestionOption, QuestionImage, AIParseResult, ExamPage
from apps.papers.models import ExamPaper
from apps.common.codegen import generate_question_system_id
from apps.common.ai.components.vision_parser import VisionParserComponent
from apps.common.ai.failure_safety import (
    PHOTO_RECOGNITION_FAILURE,
    new_safe_ai_error,
)
from apps.common.ai.image_codec import encode_image_source
from apps.common.oss_service import upload_crop_image_safe

logger = logging.getLogger(__name__)

def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


def vision_parser_component_factory() -> VisionParserComponent:
    return VisionParserComponent()


def _compress_image_for_vision(image_path: str, max_size: int = 1600) -> str:
    """Compatibility wrapper around the shared safe image codec."""
    return encode_image_source(image_path, max_edge=max_size)


def _call_vision_api(image_paths: list) -> dict:
    """Call Qwen vision API to recognize exam question content from images.

    Attempts OSS upload first; fallback to compressed base64 data URL.
    Retries up to 2 times on transient network errors.
    """
    image_sources = []
    img_path = ""
    url = ""
    parsed = None
    component = None
    failed = False
    try:
        for img_path in image_paths:
            url = upload_crop_image_safe(
                img_path, prefix='photo_questions'
            )
            image_sources.append(url or img_path)
        component = vision_parser_component_factory()
        parsed = component.recognize_photo(image_sources)
    except Exception:
        failed = True
    finally:
        close = getattr(component, 'close', None)
        if callable(close):
            close()
        image_sources.clear()
        image_paths = []
        img_path = ""
        url = ""
        component = None

    if failed:
        parsed = None
        raise new_safe_ai_error(PHOTO_RECOGNITION_FAILURE)
    return parsed


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def photo_create_question(request):
    """Upload photo(s) and create a question via AI recognition.

    When called from the "crop and recognize" flow in question-edit page,
    accepts `crop_file_path` (existing cropped image path relative to media root)
    and `page_no` to associate the new question with the source paper and page.
    """
    files = request.FILES.getlist('images')
    paper_id = request.POST.get('paper_id', '')
    crop_file_path = request.POST.get('crop_file_path', '').strip()
    page_no_str = request.POST.get('page_no', '').strip()
    page_no = int(page_no_str) if page_no_str.isdigit() else 1

    if not files and not crop_file_path:
        return Response({
            'code': 400, 'message': '请提供图片或crop_file_path', 'data': None, 'trace_id': make_trace_id()
        }, status=status.HTTP_400_BAD_REQUEST)

    logger.info(
        '[photo-create] paper_supplied=%s crop_supplied=%s page_no=%s',
        bool(paper_id),
        bool(crop_file_path),
        page_no,
    )

    try:
        # === 确定图片来源 ===
        if crop_file_path:
            # 已裁剪过的图片（框选新增流程），直接使用
            crop_abs = str(settings.MEDIA_ROOT / crop_file_path)
            if not os.path.exists(crop_abs):
                return Response({
                    'code': 400, 'message': '裁剪文件不存在',
                    'data': None, 'trace_id': make_trace_id(),
                }, status=status.HTTP_400_BAD_REQUEST)
            saved_paths = [crop_abs]
            saved_rels = [crop_file_path]
            upload_dir_name = None
        else:
            # 标准流程：上传文件保存到 photos/ 目录
            upload_dir = settings.MEDIA_ROOT / 'exams' / 'photos' / str(uuid.uuid4())
            upload_dir.mkdir(parents=True, exist_ok=True)
            upload_dir_name = upload_dir.name

            saved_paths = []
            saved_rels = []
            for f in files:
                fname = f'{uuid.uuid4().hex[:8]}_{f.name}'
                fpath = upload_dir / fname
                with open(fpath, 'wb') as dest:
                    for chunk in f.chunks():
                        dest.write(chunk)
                saved_paths.append(str(fpath))
                saved_rels.append(f'exams/photos/{upload_dir.name}/{fname}')

        start_time = time.time()
        parsed = _call_vision_api(saved_paths)
        latency_ms = int((time.time() - start_time) * 1000)

        # === 确定试卷 ===
        paper = None
        if paper_id:
            try:
                paper = ExamPaper.objects.get(id=paper_id, is_deleted=False)
            except ExamPaper.DoesNotExist:
                pass

        if not paper:
            paper = ExamPaper.objects.create(
                title=f'拍照试题_{timezone.now().strftime("%Y%m%d%H%M%S")}',
                paper_type='photo',
                subject='M',
                stage='middle',
                grade='9',
                status='reviewing',
                source_file_path=saved_rels[0],
                uploaded_by=request.user,
            )

        system_id = generate_question_system_id(paper.subject or 'M')
        question_no = str(parsed.get('question_no', '1'))
        paper_question_no = f"PHOTO-{system_id}"

        question = ExamQuestion.objects.create(
            paper=paper,
            system_id=system_id,
            paper_question_no=paper_question_no,
            question_no=question_no,
            question_type=parsed.get('question_type', 'short_answer'),
            section_title=parsed.get('section_title', ''),
            stem=parsed.get('stem', ''),
            answer=parsed.get('answer', ''),
            analysis=parsed.get('analysis', ''),
            solution=parsed.get('solution', ''),
            knowledge_points=parsed.get('knowledge_points', []),
            difficulty=parsed.get('difficulty', 3),
            page_start=page_no,
            page_end=page_no,
            confidence=parsed.get('confidence', 0.8),
            need_review=True,
            review_status='need_review',
            parse_status='photo_created',
        )

        qtype = parsed.get('question_type', '')
        if qtype in ('single_choice', 'multiple_choice'):
            for opt in parsed.get('options', []):
                QuestionOption.objects.create(
                    question=question,
                    option_label=opt.get('label', 'A'),
                    content=opt.get('content', ''),
                    sort_order=ord(opt.get('label', 'A')) - 65,
                )

        # === 关联图片 ===
        if crop_file_path and paper_id:
            # 来自框选新增：已有的裁剪图，关联到新题目
            source_page = ExamPage.objects.filter(
                paper=paper, page_no=page_no
            ).first()
            QuestionImage.objects.create(
                paper=paper,
                question=question,
                page=source_page,
                image_type='diagram',
                file_path=crop_file_path,
                source_page_image_path=source_page.image_path if source_page else crop_file_path,
                description='框选新增',
                sort_order=0,
            )
        else:
            # 标准流程：为每张上传图片创建 QuestionImage + ExamPage
            for i, rel in enumerate(saved_rels):
                QuestionImage.objects.create(
                    paper=paper,
                    question=question,
                    image_type='photo_original',
                    file_path=rel,
                    source_page_image_path=rel,
                    description=f'原图{i+1}',
                    sort_order=i,
                )
                ExamPage.objects.create(
                    paper=paper,
                    page_no=i + 1,
                    image_path=rel,
                    parse_status='converted',
                )

        AIParseResult.objects.create(
            paper=paper,
            raw_response=json.dumps(parsed),
            response_json=json.dumps(parsed),
            latency_ms=latency_ms,
            is_valid_json=True,
            model_name='qwen3-vl-plus-photo',
        )

        # AI 答案不会自动生成，需由用户在界面手动触发

        return Response({
            'code': 0,
            'message': '识别成功，可手工进行 AI 处理',
            'data': {
                'question_id': question.id,
                'system_id': system_id,
                'parsed': parsed,
                'ai_generation_status': 'not_started',
            },
            'trace_id': make_trace_id(),
        })

    except Exception:
        logger.error('Photo question creation failed')
        return Response({
            'code': 500, 'message': '识别失败，请稍后重试', 'data': None,
            'trace_id': make_trace_id(),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def photo_list_questions(request):
    """List photo-created questions with status filter."""
    review_status = request.GET.get('review_status', '')
    knowledge_point_id = request.GET.get('knowledge_point_id', '')
    search = request.GET.get('search', '')

    qs = ExamQuestion.objects.select_related('paper').filter(
        parse_status='photo_created'
    )

    if review_status:
        qs = qs.filter(review_status=review_status)
    if search:
        qs = qs.filter(stem__icontains=search)
    if knowledge_point_id:
        if knowledge_point_id == '-1':
            # "未分类": questions with empty or null knowledge_points
            qs = qs.filter(
                Q(knowledge_points__isnull=True) | Q(knowledge_points=[])
            )
        else:
            from apps.knowledge.models import KnowledgePoint
            try:
                kp_uuid = uuid.UUID(str(knowledge_point_id))
                kp = KnowledgePoint.objects.get(pk=kp_uuid)
            except (KnowledgePoint.DoesNotExist, ValueError, TypeError):
                return Response({'code': 400, 'message': 'Invalid knowledge_point_id'}, status=400)
            qs = qs.filter(
                Q(knowledge_points__contains=[{'id': str(kp.id)}]) |
                Q(knowledge_points__contains=[{'module': kp.module}])
            )

    qs = qs.order_by('-created_at')

    items = []
    for q in qs:
        kp_count = 0
        if q.knowledge_points:
            kps = q.knowledge_points
            kp_count = len(kps) if isinstance(kps, list) else 0
        elif q.ai_knowledge_enrichment:
            ench = q.ai_knowledge_enrichment
            if isinstance(ench, dict):
                kp_count = len(ench.get('points', ench.get('matched_points', [])))

        stem_preview = ''
        if q.stem:
            stem_preview = q.stem[:20] + ('...' if len(q.stem) > 20 else '')

        def _ai_confirmed(field_val):
            return bool(field_val and isinstance(field_val, dict) and field_val.get('confirmed'))

        items.append({
            'id': q.id,
            'system_id': q.system_id or '',
            'question_no': q.question_no,
            'question_type': q.question_type,
            'stem_preview': stem_preview,
            'difficulty': int(q.difficulty) if q.difficulty else 0,
            'knowledge_points_count': kp_count,
            'review_status': q.review_status,
            'parse_status': q.parse_status,
            'confidence': float(q.confidence) if q.confidence else 0,
            'ai_answer_a': bool(q.ai_answer_a),
            'ai_answer_b': bool(q.ai_answer_b),
            'ai_answer_c': bool(q.ai_answer_c),
            'ai_answer_a_confirmed': _ai_confirmed(q.ai_answer_a),
            'ai_answer_b_confirmed': _ai_confirmed(q.ai_answer_b),
            'ai_answer_c_confirmed': _ai_confirmed(q.ai_answer_c),
            'created_at': q.created_at.isoformat() if q.created_at else '',
        })

    return Response({
        'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
        'data': items,
    })
