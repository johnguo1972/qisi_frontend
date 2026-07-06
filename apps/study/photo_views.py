"""API views for photo-based question creation."""
import logging
import os
import json
import time
import uuid
import httpx
import base64
import re
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
from apps.common.oss_service import upload_crop_image_safe

logger = logging.getLogger(__name__)

QWEN_VL_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


SYSTEM_PROMPT = """你是一个专业的试题识别专家。请分析图片中的试题内容，提取以下结构化信息并返回JSON：
{
  "question_no": "题号",
  "question_type": "single_choice|multiple_choice|fill_blank|short_answer|essay|true_false|computation|proof",
  "section_title": "大题标题",
  "stem": "题干内容",
  "options": [{"label": "A", "content": "选项内容"}],
  "answer": "答案",
  "analysis": "解析",
  "solution": "解答",
  "knowledge_points": ["知识点1"],
  "difficulty": 3,
  "images": [{"description": "插图描述"}],
  "confidence": 0.9
}
要求：只输出JSON；LaTeX公式用$...$包裹；difficulty为1-5整数；confidence为0-1浮点数"""


def _compress_image_for_vision(image_path: str, max_size: int = 1600) -> str:
    """Compress and resize an image for vision API, returning a base64 data URL.

    Resizes to at most max_size on the longest edge and converts to JPEG.
    This avoids sending overly large base64 payloads to the API.
    """
    from PIL import Image, UnidentifiedImageError
    import io

    try:
        img = Image.open(image_path)
        # Convert RGBA/P to RGB for JPEG
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        # Resize if too large
        w, h = img.size
        if max(w, h) > max_size:
            ratio = max_size / max(w, h)
            new_w = int(w * ratio)
            new_h = int(h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f'data:image/jpeg;base64,{b64}'
    except (UnidentifiedImageError, OSError) as e:
        logger.warning(f'Image compression failed for {image_path}: {e}')
        # Fallback: original base64
        with open(image_path, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        ext = os.path.splitext(image_path)[1].lstrip('.')
        mime = f'image/{ext}' if ext in ('png', 'jpeg', 'jpg', 'webp') else 'image/png'
        return f'data:{mime};base64,{b64}'


def _call_vision_api(image_paths: list) -> dict:
    """Call Qwen vision API to recognize exam question content from images.

    Attempts OSS upload first; fallback to compressed base64 data URL.
    Retries up to 2 times on transient network errors.
    """
    api_key = os.environ.get('QWEN_API_KEY', '')
    if not api_key:
        raise Exception("QWEN_API_KEY is not set")

    content = [{"type": "text", "text": "请识别图片中的试题内容，按JSON格式返回。"}]
    for img_path in image_paths:
        url = upload_crop_image_safe(img_path, prefix='photo_questions')
        if not url:
            # OSS unavailable — compress and inline as base64
            url = _compress_image_for_vision(img_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": url}
        })

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
    payload = {
        "model": "qwen3-vl-plus",
        "messages": messages,
        "max_tokens": 8000,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error = None
    for attempt in range(1, 4):
        try:
            with httpx.Client(timeout=120.0, trust_env=False) as client:
                resp = client.post(QWEN_VL_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()
            reply = body['choices'][0]['message']['content']

            try:
                return json.loads(reply)
            except json.JSONDecodeError:
                m = re.search(r'\{[\s\S]*\}', reply)
                if m:
                    return json.loads(m.group())
                raise ValueError(f"AI response is not valid JSON: {reply[:200]}")
        except httpx.TimeoutException:
            last_error = 'AI识别服务响应超时，请稍后重试'
            logger.warning(f'Vision API timeout (attempt {attempt}/3)')
            time.sleep(3 * attempt)
        except httpx.RemoteProtocolError as e:
            last_error = f'AI识别服务连接断开: {e}'
            logger.warning(f'Vision API disconnected (attempt {attempt}/3): {e}')
            time.sleep(3 * attempt)
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code if e.response else 'unknown'
            last_error = f'AI识别服务返回错误 (HTTP {status_code})'
            logger.warning(f'Vision API HTTP error (attempt {attempt}/3): {e}')
            time.sleep(3 * attempt)
        except httpx.HTTPError as e:
            last_error = f'AI识别服务网络错误: {e}'
            logger.warning(f'Vision API network error (attempt {attempt}/3): {e}')
            time.sleep(3 * attempt)

    raise Exception(last_error or 'AI识别服务调用失败（已重试3次）')


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

    logger.info(f'[photo-create] paper_id={paper_id!r} crop_file_path={crop_file_path!r} page_no={page_no}')

    try:
        # === 确定图片来源 ===
        if crop_file_path:
            # 已裁剪过的图片（框选新增流程），直接使用
            crop_abs = str(settings.MEDIA_ROOT / crop_file_path)
            if not os.path.exists(crop_abs):
                return Response({
                    'code': 400, 'message': f'裁剪文件不存在: {crop_file_path}',
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

        return Response({
            'code': 0,
            'message': '识别成功',
            'data': {
                'question_id': question.id,
                'system_id': system_id,
                'parsed': parsed,
            },
            'trace_id': make_trace_id(),
        })

    except Exception as e:
        logger.exception(f'Photo question creation failed: {e}')
        return Response({
            'code': 500, 'message': f'识别失败: {str(e)}', 'data': None, 'trace_id': make_trace_id()
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
        try:
            kp_id = int(knowledge_point_id)
            if kp_id == -1:
                # "未分类": questions with empty or null knowledge_points
                qs = qs.filter(
                    Q(knowledge_points__isnull=True) | Q(knowledge_points=[])
                )
            else:
                qs = qs.filter(knowledge_points__contains=[{'id': kp_id}])
        except (ValueError, TypeError):
            pass

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
