"""Teacher APIs for P2 question/knowledge-point matching."""
import uuid
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from apps.accounts.auth import get_request_role
from apps.common.p2_api import success
from apps.parser.models import ExamQuestion
from apps.study.question_views import _teacher_question_scope_error
from .matching import rebuild_question_matches, suggest_matches, RULE_VERSION
from .models import KnowledgePoint, QuestionKnowledgeMatch
from .teacher_scope import resolve_teacher_question_scope


def _require_teacher(request):
    if get_request_role(request) != 'teacher':
        raise PermissionDenied('只有教师可以管理题目知识点匹配')


def _question(request, question_id):
    try:
        question = ExamQuestion.objects.select_related('paper').get(pk=question_id)
    except (ExamQuestion.DoesNotExist, DjangoValidationError, ValueError, TypeError):
        raise NotFound('题目不存在')
    error = _teacher_question_scope_error(request, question)
    if error:
        raise PermissionDenied('题目不在教师教学范围内')
    return question


def _point_data(item):
    point = item['knowledge_point'] if isinstance(item, dict) else item.knowledge_point
    return None if point is None else {
        'id': point.id, 'subject': point.subject, 'stage': point.stage,
        'grade_index': point.grade_index, 'grade_name': point.grade_name,
        'chapter': point.chapter, 'module': point.module, 'content': point.content,
    }


def _match_data(match):
    return {
        'id': str(match.id), 'question_id': str(match.question_id),
        'knowledge_point': _point_data(match), 'source': match.source,
        'source_version': match.source_version, 'confidence': match.confidence,
        'status': match.status, 'evidence': match.evidence or {},
        'confirmed_by': str(match.confirmed_by_id) if match.confirmed_by_id else None,
        'confirmed_at': match.confirmed_at,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def knowledge_match_preview(request):
    _require_teacher(request)
    ids = request.data.get('question_ids') or ([request.data.get('question_id')] if request.data.get('question_id') else [])
    if not isinstance(ids, list) or not ids:
        raise ValidationError('question_ids 不能为空')
    output = []
    for question_id in ids:
        question = _question(request, question_id)
        scope = resolve_teacher_question_scope(request, requested_subject=question.subject or question.paper.subject)
        output.append({
            'question_id': str(question.id),
            'matches': [{
                'knowledge_point': _point_data(item), 'source': 'rule',
                'source_version': RULE_VERSION, 'confidence': item['confidence'],
                'status': 'suggested', 'evidence': item['evidence'],
            } for item in suggest_matches(question, scope.stages if scope else ())],
        })
    return success(output)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def knowledge_match_rebuild(request, question_id):
    _require_teacher(request)
    question = _question(request, question_id)
    scope = resolve_teacher_question_scope(request, requested_subject=question.subject or question.paper.subject)
    matches = rebuild_question_matches(question, scope.stages if scope else ())
    return success({'question_id': str(question.id), 'matches': [_match_data(item) for item in matches]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def knowledge_match_rebuild_batch(request):
    """Backfill suggested matches for legacy questions without knowledge data."""
    _require_teacher(request)
    requested = request.data.get('question_ids')
    try:
        limit = min(max(int(request.data.get('limit', 500)), 1), 2000)
    except (TypeError, ValueError):
        raise ValidationError('limit 必须是 1 到 2000 之间的整数')
    if requested is not None and not isinstance(requested, list):
        raise ValidationError('question_ids 必须是数组')
    requested_ids = []
    for question_id in requested or []:
        try:
            requested_ids.append(str(uuid.UUID(str(question_id))))
        except (ValueError, AttributeError, TypeError):
            raise ValidationError('question_ids 包含无效题目 ID')
    qs = ExamQuestion.objects.select_related('paper').order_by('created_at')
    if requested_ids:
        qs = qs.filter(id__in=requested_ids)
    created = []
    skipped = 0
    processed = 0
    for question in qs[:limit]:
        if question.knowledge_points:
            skipped += 1
            continue
        if _teacher_question_scope_error(request, question):
            skipped += 1
            continue
        scope = resolve_teacher_question_scope(request, requested_subject=question.subject or question.paper.subject)
        existing = QuestionKnowledgeMatch.objects.filter(
            question=question, source='rule', source_version=RULE_VERSION,
        ).exists()
        if existing:
            skipped += 1
            continue
        processed += 1
        created.extend(rebuild_question_matches(question, scope.stages if scope else ()))
    return success({
        'processed': processed, 'created_match_count': len(created), 'skipped': skipped,
        'matches': [_match_data(item) for item in created],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def knowledge_match_pending(request):
    _require_teacher(request)
    qs = QuestionKnowledgeMatch.objects.filter(
        source='rule', source_version=RULE_VERSION, status='suggested',
    ).select_related('question__paper', 'knowledge_point')
    rows = []
    for match in qs:
        if not _teacher_question_scope_error(request, match.question):
            rows.append(_match_data(match))
    return success(rows)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def knowledge_match_batch_confirm(request):
    _require_teacher(request)
    items = request.data.get('matches') or []
    if not isinstance(items, list) or not items:
        raise ValidationError('matches 不能为空')
    changed = []
    for payload in items:
        match_id = payload.get('id') if isinstance(payload, dict) else payload
        try:
            match = QuestionKnowledgeMatch.objects.select_related('question__paper', 'knowledge_point').get(pk=match_id)
        except (QuestionKnowledgeMatch.DoesNotExist, DjangoValidationError, ValueError, TypeError):
            raise NotFound('匹配记录不存在')
        _question(request, match.question_id)
        new_status = payload.get('status', 'confirmed') if isinstance(payload, dict) else 'confirmed'
        if new_status not in {'confirmed', 'rejected'}:
            raise ValidationError('status 只能是 confirmed 或 rejected')
        if new_status == 'confirmed' and match.knowledge_point is None:
            raise ValidationError('未匹配到知识点的记录不能确认')
        match.status = new_status
        match.confirmed_by = request.user
        match.confirmed_at = timezone.now()
        match.save(update_fields=['status', 'confirmed_by', 'confirmed_at', 'updated_at'])
        if new_status == 'confirmed':
            question = match.question
            legacy = list(question.knowledge_points or [])
            ids = {str(item.get('id')) for item in legacy if isinstance(item, dict) and item.get('id') is not None}
            if str(match.knowledge_point_id) not in ids:
                legacy.append({'id': match.knowledge_point_id, 'module': match.knowledge_point.module, 'chapter': match.knowledge_point.chapter, 'grade_name': match.knowledge_point.grade_name})
                question.knowledge_points = legacy
                question.save(update_fields=['knowledge_points', 'updated_at'])
        changed.append(_match_data(match))
    return success(changed)
