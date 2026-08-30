"""P2 handout APIs: immutable question snapshots and PDF export."""
import re
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from apps.accounts.auth import get_request_role
from apps.common.p2_api import success
from apps.common.media import media_url
from apps.common.subject_codes import normalize_subject_code
from apps.courses.models import Course
from apps.courses.views import _can_access_shared_course, _can_edit_course, _get_course_or_404
from apps.parser.models import ExamQuestion, QuestionImage
from apps.study.question_views import _teacher_question_scope_error
from .models import Handout, HandoutQuestion
from .serializers import HandoutQuestionSerializer, HandoutSerializer


PUBLISHABLE_REVIEW_STATUSES = {'confirmed', 'published', 'approved'}


def _require_teacher(request):
    if get_request_role(request) != 'teacher':
        raise PermissionDenied('只有教师可以管理讲义')


def _get_handout(handout_id):
    try:
        return Handout.objects.select_related('course', 'creator_teacher').get(pk=handout_id)
    except Handout.DoesNotExist:
        raise NotFound('讲义不存在')


def _can_read(handout, user):
    return handout.creator_teacher_id == user.id or (handout.course_id and _can_access_shared_course(handout.course, user))


def _can_write(handout, user):
    return handout.creator_teacher_id == user.id or (handout.course_id and _can_edit_course(handout.course, user))


def _question_for_teacher(request, question_id):
    try:
        question = ExamQuestion.objects.select_related('paper').get(pk=question_id)
    except (ExamQuestion.DoesNotExist, DjangoValidationError, ValueError, TypeError):
        raise NotFound('题目不存在')
    if _teacher_question_scope_error(request, question):
        raise PermissionDenied('题目不在教师教学范围内')
    if question.review_status not in PUBLISHABLE_REVIEW_STATUSES:
        raise ValidationError(f'题目 {question_id} 尚未达到讲义发布状态')
    return question


def _snapshot(question):
    options = [
        {'label': item.option_label, 'content': item.content, 'content_html': item.content_html or ''}
        for item in question.options.order_by('sort_order', 'id')
    ]
    images = [
        {
            'id': str(item.id), 'file_path': item.file_path, 'url': media_url(item.file_path),
            'image_type': item.image_type, 'placement': item.placement,
            'sort_order': item.sort_order, 'display_width': item.display_width,
        }
        for item in question.images.exclude(image_type='formula').order_by('sort_order', 'id')
    ]
    return {
        'id': str(question.id), 'question_no': question.question_no,
        'paper_question_no': question.paper_question_no or '', 'question_type': question.question_type,
        'subject': question.subject or question.paper.subject or '',
        'stem': question.stem, 'stem_html': question.stem_html or '',
        'material': question.material or '', 'subquestions': question.subquestions or [],
        'tables': question.tables or [], 'answer': question.answer or '',
        'analysis': question.analysis or '', 'solution': question.solution or '',
        'difficulty': str(question.difficulty) if question.difficulty is not None else None,
        'knowledge_points': question.knowledge_points or [], 'options_html': options,
        'image_items': images, 'image_urls': [item['file_path'] for item in images],
    }


def _question_ids(payload):
    raw = payload.get('question_ids')
    if raw is None:
        raw = [item.get('question_id') for item in (payload.get('questions') or []) if isinstance(item, dict)]
    if not isinstance(raw, list) or not raw:
        raise ValidationError('question_ids 不能为空')
    result = []
    for item in raw:
        value = str(item).strip()
        if value and value not in result:
            result.append(value)
    if not result:
        raise ValidationError('question_ids 不能为空')
    return result


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def handout_list_or_create(request):
    _require_teacher(request)
    if request.method == 'GET':
        rows = []
        for handout in Handout.objects.select_related('course', 'creator_teacher'):
            if _can_read(handout, request.user):
                rows.append(handout)
        return success(HandoutSerializer(rows, many=True).data)

    payload = request.data.copy()
    subject = normalize_subject_code(payload.get('subject'))
    if not subject:
        raise ValidationError('subject 不受支持')
    course = None
    if payload.get('course'):
        course = _get_course_or_404(payload['course'])
        if not _can_edit_course(course, request.user):
            raise PermissionDenied('没有权限关联该课程')
    handout = Handout.objects.create(
        name=str(payload.get('name') or '').strip(), subject=subject,
        stage=str(payload.get('stage') or ''), grade=str(payload.get('grade') or ''),
        creator_teacher=request.user, course=course,
    )
    if not handout.name:
        handout.delete()
        raise ValidationError('name 不能为空')
    return success(HandoutSerializer(handout).data, status=201)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def handout_detail(request, handout_id):
    _require_teacher(request)
    handout = _get_handout(handout_id)
    if not _can_read(handout, request.user):
        raise PermissionDenied('没有权限访问该讲义')
    if request.method == 'GET':
        return success(HandoutSerializer(handout).data)
    if not _can_write(handout, request.user):
        raise PermissionDenied('没有权限修改该讲义')
    if request.method == 'DELETE':
        handout.status = 'archived'
        handout.save(update_fields=['status', 'updated_at'])
        return success(HandoutSerializer(handout).data)
    for field in ('name', 'stage', 'grade'):
        if field in request.data:
            value = str(request.data[field] or '').strip()
            if field == 'name' and not value:
                raise ValidationError('name 不能为空')
            setattr(handout, field, value)
    handout.save()
    return success(HandoutSerializer(handout).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def handout_replace_questions(request, handout_id):
    _require_teacher(request)
    handout = _get_handout(handout_id)
    if not _can_write(handout, request.user):
        raise PermissionDenied('没有权限修改该讲义')
    if handout.status == 'published':
        raise ValidationError('已发布讲义不可直接修改，请创建新版本')
    ids = _question_ids(request.data)
    source_types = request.data.get('source_types') or {}
    question_rows = []
    for index, question_id in enumerate(ids, 1):
        question = _question_for_teacher(request, question_id)
        source_type = source_types.get(str(question.id), 'question_bank') if isinstance(source_types, dict) else 'question_bank'
        if source_type not in {'question_bank', 'course', 'ai', 'manual'}:
            raise ValidationError('source_type 不受支持')
        question_rows.append((index, question, source_type))
    with transaction.atomic():
        handout.questions.all().delete()
        HandoutQuestion.objects.bulk_create([
            HandoutQuestion(
                handout=handout, question=question, sort_no=index,
                source_type=source_type, display_snapshot=_snapshot(question),
            ) for index, question, source_type in question_rows
        ])
        handout.version = handout.version + 1 if handout.questions.exists() else handout.version
        handout.save(update_fields=['version', 'updated_at'])
    return success(HandoutQuestionSerializer(handout.questions.all(), many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def handout_preview(request, handout_id):
    _require_teacher(request)
    handout = _get_handout(handout_id)
    if not _can_read(handout, request.user):
        raise PermissionDenied('没有权限访问该讲义')
    questions = HandoutQuestionSerializer(handout.questions.all(), many=True).data
    return success({'handout': HandoutSerializer(handout).data, 'questions': questions})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def handout_publish(request, handout_id):
    _require_teacher(request)
    handout = _get_handout(handout_id)
    if not _can_write(handout, request.user):
        raise PermissionDenied('没有权限发布该讲义')
    if not handout.course_id:
        raise ValidationError('讲义发布前必须关联课程或班级')
    if not handout.questions.exists():
        raise ValidationError('讲义至少需要一道题目')
    handout.status = 'published'
    handout.save(update_fields=['status', 'updated_at'])
    return success(HandoutSerializer(handout).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def handout_export_pdf(request, handout_id):
    _require_teacher(request)
    handout = _get_handout(handout_id)
    if not _can_read(handout, request.user):
        raise PermissionDenied('没有权限导出该讲义')
    rows = list(handout.questions.all())
    if not rows:
        raise ValidationError('讲义至少需要一道题目')
    from apps.study.student_views import _build_pdf
    questions = []
    for row in rows:
        item = dict(row.display_snapshot or {})
        item['_pdf_title'] = handout.name
        questions.append(item)
    safe_name = re.sub(r'[\\/:*?"<>|]+', '_', handout.name).strip(' ._')[:60] or 'handout'
    relative_path = f'exports/{safe_name}_{handout.id}.pdf'
    output_path = Path(settings.MEDIA_ROOT) / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_build_pdf('handout', questions, False, '', render_formulas=True))
    handout.pdf_file_path = relative_path
    handout.save(update_fields=['pdf_file_path', 'updated_at'])
    return success({'pdf_file_path': relative_path, 'download_url': f"{settings.MEDIA_URL.rstrip('/')}/{relative_path}"})
