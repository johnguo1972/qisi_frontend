"""Question search/detail/update/publish views."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, CharField
from django.db.models.functions import Cast
from apps.accounts.auth import get_request_role
from apps.parser.models import ExamQuestion
from apps.study.models import QuestionRelation, QuestionTagRelation
from apps.knowledge.models import KnowledgePoint
from apps.knowledge.teacher_scope import (
    TeachingScopeForbidden,
    apply_stage_scope,
    resolve_teacher_question_scope,
)
from apps.common.question_display import preview_text
from .question_relation_service import (
    canonical_question_pair,
    find_relation_candidates,
    knowledge_point_keys,
)
from .serializers import QuestionListSerializer, QuestionDetailSerializer


SUBJECT_LABELS = {
    'math': '数学',
    'physics': '物理',
    'chinese': '语文',
    'english': '英语',
    'chemistry': '化学',
}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_list(request):
    """Q-05: Question search/list with filters."""
    subject = request.GET.get('subject')
    difficulty = request.GET.get('difficulty')
    question_type = request.GET.get('question_type')
    keyword = request.GET.get('keyword', '').strip()
    tag = request.GET.get('tag', '').strip()
    question_uuid = request.GET.get('uuid', '').strip()
    knowledge = request.GET.get('knowledge')
    question_no = request.GET.get('question_no')
    review_status = request.GET.get('review_status')
    paper_id = request.GET.get('paper_id')
    knowledge_point_id = request.GET.get('knowledge_point_id', '')
    stages = request.GET.get('stages', '')

    try:
        scope = resolve_teacher_question_scope(
            request,
            requested_subject=subject or '',
            requested_stages=stages,
        )
    except TeachingScopeForbidden:
        return Response({
            'code': 'TEACHING_SCOPE_FORBIDDEN',
            'message': 'Requested subject or stage is outside the teacher teaching scope.',
            'data': None,
            'trace_id': '',
        }, status=403)

    if scope is not None and not scope.configured:
        try:
            page = max(int(request.GET.get('page', 1)), 1)
            page_size = min(max(int(request.GET.get('page_size', 20)), 1), 100)
        except (TypeError, ValueError):
            return Response({'code': 400, 'message': 'page/page_size 参数无效', 'data': None}, status=400)
        return Response({
            'code': 0, 'message': 'success', 'trace_id': '',
            'data': {
                'items': [], 'total': 0, 'page_no': page, 'page_size': page_size,
                'scope_configured': False,
            }
        })

    if scope is not None:
        subject = scope.selected_subject

    qs = ExamQuestion.objects.select_related('paper').all()

    if review_status:
        qs = qs.filter(review_status=review_status)
    if subject:
        if scope is not None:
            qs = qs.filter(subject__in=[subject, SUBJECT_LABELS.get(subject, subject)])
        else:
            qs = qs.filter(subject=subject)
    if difficulty:
        diff_values = [value.strip() for value in difficulty.split(',') if value.strip()]
        try:
            diff_values = [float(value) for value in diff_values]
            if len(diff_values) == 1:
                qs = qs.filter(difficulty=diff_values[0])
            elif diff_values:
                qs = qs.filter(difficulty__in=diff_values)
        except (ValueError, TypeError):
            pass
    if question_type:
        question_types = [value.strip() for value in question_type.split(',') if value.strip()]
        if len(question_types) == 1:
            qs = qs.filter(question_type=question_types[0])
        elif question_types:
            qs = qs.filter(question_type__in=question_types)
    if tag:
        tag_question_ids = QuestionTagRelation.objects.filter(tag__name=tag).values('question_id')
        qs = qs.filter(Q(tags__contains=[tag]) | Q(id__in=tag_question_ids))
    if keyword:
        qs = qs.filter(
            Q(stem__icontains=keyword)
            | Q(stem_html__icontains=keyword)
            | Q(question_no__icontains=keyword)
            | Q(paper_question_no__icontains=keyword)
            | Q(system_id__icontains=keyword)
            | Q(options__content__icontains=keyword)
        ).distinct()
    if question_uuid:
        # UUID 字段不能直接使用字符串 icontains；转换为文本后支持输入完整 UUID
        # 或任意片段的模糊查询，例如前 8 位、后 6 位等。
        qs = qs.annotate(uuid_text=Cast('id', output_field=CharField())).filter(
            uuid_text__icontains=question_uuid
        )
    if question_no:
        qs = qs.filter(
            Q(question_no__icontains=question_no) |
            Q(paper_question_no__icontains=question_no) |
            Q(system_id__icontains=question_no)
        )
    if paper_id:
        try:
            qs = qs.filter(paper_id=int(paper_id))
        except (ValueError, TypeError):
            pass
    if knowledge:
        qs = qs.filter(ai_knowledge_enrichment__contains=[{'code': knowledge}])

    if scope is not None:
        qs = apply_stage_scope(qs, scope.stages)
    elif stages:
        stage_query = Q()
        for value in stages.split(','):
            # The teacher page displays a combined grade/term label while
            # imported papers store grade/stage separately.
            for part in value.strip().split():
                if part:
                    stage_query |= Q(paper__grade__icontains=part) | Q(paper__stage__icontains=part)
        if stage_query:
            qs = qs.filter(stage_query)

    # Filter by the manually associated knowledge point first.  The older
    # AI-enrichment fallback is retained for questions that only have AI data.
    if knowledge_point_id:
        kp_values = [value.strip() for value in knowledge_point_id.split(',') if value.strip()]
        if '-1' in kp_values:
            qs = qs.filter(Q(knowledge_points__isnull=True) | Q(knowledge_points=[]))
        else:
            kp_query = Q()
            for value in kp_values:
                # Knowledge-point IDs in the current production data are UUID
                # strings.  JSON containment must be applied before attempting
                # the legacy BIGINT KnowledgePoint lookup, otherwise UUID
                # requests leave kp_query empty and silently return all items.
                kp_query |= (
                    Q(knowledge_points__contains=[{'id': value}])
                    | Q(ai_knowledge_enrichment__contains={
                        'knowledge_points': [{'id': value}]
                    })
                )
                try:
                    kp_id = int(value)
                    kp_query |= (
                        Q(knowledge_points__contains=[{'id': kp_id}]) |
                        Q(knowledge_points__contains=[{'id': str(kp_id)}]) |
                        Q(ai_knowledge_enrichment__contains=[{'id': kp_id}])
                    )
                    try:
                        kp = KnowledgePoint.objects.get(pk=kp_id)
                        kp_query |= Q(knowledge_points__contains=[{'module': kp.module}])
                    except KnowledgePoint.DoesNotExist:
                        pass
                except (ValueError, TypeError):
                    try:
                        kp = KnowledgePoint.objects.get(pk=value)
                        kp_query |= Q(knowledge_points__contains=[{'module': kp.module}])
                    except (KnowledgePoint.DoesNotExist, ValueError, TypeError):
                        continue
            if kp_query:
                qs = qs.filter(kp_query)

    try:
        page = max(int(request.GET.get('page', 1)), 1)
        page_size = min(max(int(request.GET.get('page_size', 20)), 1), 100)
    except (TypeError, ValueError):
        return Response({'code': 400, 'message': 'page/page_size 参数无效', 'data': None}, status=400)

    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size

    items = qs.order_by('sort_order', 'id')[start:end]
    return Response({
        'code': 0, 'message': 'success', 'trace_id': '',
        'data': {
            'items': QuestionListSerializer(items, many=True).data,
            'total': total,
            'page_no': page,
            'page_size': page_size,
        }
    })


def _teacher_question_scope_error(request, question):
    """Apply the same teaching scope to UUID-based question operations."""
    if get_request_role(request) != 'teacher':
        return None
    try:
        scope = resolve_teacher_question_scope(
            request,
            requested_subject=question.subject or '',
        )
    except TeachingScopeForbidden:
        return Response({
            'code': 'TEACHING_SCOPE_FORBIDDEN',
            'message': 'Question is outside the teacher teaching scope.',
            'data': None,
            'trace_id': '',
        }, status=403)
    if scope is None or not scope.configured:
        return Response({
            'code': 'TEACHING_SCOPE_FORBIDDEN',
            'message': 'Teacher teaching scope is not configured.',
            'data': None,
            'trace_id': '',
        }, status=403)
    if not apply_stage_scope(
        ExamQuestion.objects.filter(pk=question.pk), scope.stages
    ).exists():
        return Response({
            'code': 'TEACHING_SCOPE_FORBIDDEN',
            'message': 'Question is outside the teacher teaching scope.',
            'data': None,
            'trace_id': '',
        }, status=403)
    return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def similar_questions(request, question_id):
    """Return questions with the same main knowledge point and similar difficulty."""
    try:
        question = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None}, status=404)

    scope_error = _teacher_question_scope_error(request, question)
    if scope_error:
        return scope_error

    raw_points = question.knowledge_points or []
    if isinstance(raw_points, dict):
        raw_points = raw_points.get('points', [])
    main_point = next((item for item in raw_points if isinstance(item, dict) and (item.get('module') or item.get('id'))), None)
    modules = [main_point.get('module')] if main_point and main_point.get('module') else []
    ids = [main_point.get('id')] if main_point and main_point.get('id') else []
    query = Q()
    for module in modules:
        query |= Q(knowledge_points__contains=[{'module': module}])
    for point_id in ids:
        query |= Q(knowledge_points__contains=[{'id': point_id}])

    candidates = ExamQuestion.objects.exclude(pk=question.pk).filter(subject=question.subject)
    if not modules and not ids:
        return Response({'code': 0, 'data': []})
    candidates = candidates.filter(query)
    if get_request_role(request) == 'teacher':
        scope = resolve_teacher_question_scope(request, requested_subject=question.subject)
        candidates = apply_stage_scope(candidates, scope.stages)
    if question.difficulty is not None:
        candidates = candidates.filter(
            difficulty__gte=max(0, float(question.difficulty) - 1),
            difficulty__lte=float(question.difficulty) + 1,
        )

    items = candidates.order_by('difficulty', 'sort_order')[:20]
    return Response({'code': 0, 'data': QuestionListSerializer(items, many=True).data})


def _relation_response(data):
    return Response({'code': 0, 'message': 'success', 'data': data, 'trace_id': ''})


def _relation_not_found_response():
    return Response(
        {'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': ''},
        status=404,
    )


def _question_bank_manager_error(request):
    if get_request_role(request) in {'admin', 'teacher'}:
        return None
    return Response({
        'code': 'QUESTION_BANK_MANAGEMENT_FORBIDDEN',
        'message': 'Only question bank managers can change question relations.',
        'data': None,
        'trace_id': '',
    }, status=403)


def _get_visible_question(request, question_id):
    try:
        question = ExamQuestion.objects.select_related('paper').get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return None, _relation_not_found_response()
    scope_error = _teacher_question_scope_error(request, question)
    if scope_error:
        return None, scope_error
    return question, None


def _get_visible_question_pair(request, question_id, related_id):
    question, error = _get_visible_question(request, question_id)
    if error:
        return None, None, error
    related, error = _get_visible_question(request, related_id)
    if error:
        return None, None, error
    return question, related, None


def _visible_relation_questions(request, origin_question):
    questions = ExamQuestion.objects.select_related('paper').all()
    if get_request_role(request) == 'teacher':
        scope = resolve_teacher_question_scope(
            request,
            requested_subject=origin_question.subject or '',
        )
        questions = questions.filter(
            subject__in=[
                scope.selected_subject,
                SUBJECT_LABELS.get(scope.selected_subject, scope.selected_subject),
            ]
        )
        questions = apply_stage_scope(questions, scope.stages)
    return questions


def _common_knowledge_point_names(question, related_question):
    common_keys = knowledge_point_keys(question.knowledge_points) & knowledge_point_keys(
        related_question.knowledge_points
    )
    names = []
    raw_points = question.knowledge_points or []
    if isinstance(raw_points, dict):
        raw_points = raw_points.get('points') or raw_points.get('knowledge_points') or [raw_points]
    if not isinstance(raw_points, (list, tuple)):
        return names
    for point in raw_points:
        if isinstance(point, dict):
            for field in ('id', 'module', 'name'):
                value = point.get(field)
                if value is not None and str(value).strip():
                    if f'{field}:{str(value).strip()}' in common_keys:
                        name = str(value).strip()
                        if name not in names:
                            names.append(name)
                    break
        elif isinstance(point, str) and point.strip() and f'name:{point.strip()}' in common_keys:
            if point.strip() not in names:
                names.append(point.strip())
    return names


def _relation_knowledge_points_display(questions):
    """Build existing knowledge-point display values with bounded page queries."""
    raw_points_by_id = {}
    numeric_ids = set()
    modules = set()
    for question in questions:
        raw_points = question.knowledge_points or question.ai_knowledge_enrichment or []
        if isinstance(raw_points, dict):
            raw_points = raw_points.get('points') or raw_points.get('knowledge_points') or []
        if not isinstance(raw_points, list):
            raw_points = []
        raw_points_by_id[question.id] = raw_points
        for point in raw_points:
            if not isinstance(point, dict):
                continue
            if point.get('module'):
                modules.add(point['module'])
            point_id = point.get('id')
            if isinstance(point_id, bool):
                continue
            try:
                numeric_ids.add(int(point_id))
            except (TypeError, ValueError, OverflowError):
                continue

    if numeric_ids or modules:
        points = list(KnowledgePoint.objects.filter(
            Q(id__in=numeric_ids) | Q(module__in=modules)
        ))
    else:
        points = []
    points_by_id = {str(point.id): point for point in points}
    displays = {}
    for question in questions:
        raw_points = raw_points_by_id[question.id]
        question_modules = {
            point.get('module') for point in raw_points
            if isinstance(point, dict) and point.get('module')
        }
        subject_points = [
            point for point in points
            if point.subject == question.subject and point.module in question_modules
        ]
        module_points = subject_points or [
            point for point in points if point.module in question_modules
        ]
        result = []
        seen = set()
        for item in raw_points:
            module = item.get('module') if isinstance(item, dict) else None
            key = str(item.get('id')) if isinstance(item, dict) and item.get('id') is not None else None
            point = points_by_id.get(key)
            if point is None and module:
                point = next((item for item in module_points if item.module == module), None)
            name = point.module if point else module
            if name and name not in seen:
                result.append({'id': str(point.id) if point else key, 'name': name})
                seen.add(name)
        displays[question.id] = result
    return displays


def _relation_item(question, common_names=None, knowledge_points_display=None):
    return {
        'id': str(question.id),
        'question_no': question.question_no,
        'stem_preview': preview_text(question.stem, question.subquestions, question.tables, limit=120),
        'difficulty': question.difficulty,
        'knowledge_points_display': (
            QuestionListSerializer(question).get_knowledge_points_display(question)
            if knowledge_points_display is None else knowledge_points_display
        ),
        'common_knowledge_point_names': common_names or [],
    }


def _relation_pagination(request):
    try:
        page = max(int(request.GET.get('page', 1)), 1)
        page_size = min(max(int(request.GET.get('page_size', 50)), 1), 100)
    except (TypeError, ValueError):
        return None, Response(
            {'code': 400, 'message': 'page/page_size 参数无效', 'data': None, 'trace_id': ''},
            status=400,
        )
    return (page, page_size), None


def _relation_page_data(total, page, page_size, items):
    return {
        'items': items,
        'total': total,
        'page_no': page,
        'page_size': page_size,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def question_relations(request, question_id):
    if request.method == 'POST':
        manager_error = _question_bank_manager_error(request)
        if manager_error:
            return manager_error

    question, error = _get_visible_question(request, question_id)
    if error:
        return error

    if request.method == 'GET':
        pagination, page_error = _relation_pagination(request)
        if page_error:
            return page_error
        page, page_size = pagination
        related_ids = []
        for relation in QuestionRelation.for_question(question):
            related_ids.append(
                relation.question_right_id if relation.question_left_id == question.id else relation.question_left_id
            )
        visible_related = _visible_relation_questions(request, question).filter(pk__in=related_ids)
        total = visible_related.count()
        start = (page - 1) * page_size
        page_questions = list(visible_related.order_by('sort_order', 'id')[start:start + page_size])
        displays = _relation_knowledge_points_display(page_questions)
        items = [
            _relation_item(item, knowledge_points_display=displays[item.id])
            for item in page_questions
        ]
        return _relation_response(_relation_page_data(total, page, page_size, items))

    question_ids = request.data.get('question_ids')
    if not isinstance(question_ids, list):
        return Response({
            'code': 400,
            'message': 'question_ids 必须是数组',
            'data': None,
            'trace_id': '',
        }, status=400)

    unique_question_ids = []
    seen_question_ids = set()
    for raw_question_id in question_ids:
        raw_value = str(raw_question_id)
        if raw_value not in seen_question_ids:
            seen_question_ids.add(raw_value)
            unique_question_ids.append(raw_question_id)
    if len(unique_question_ids) > 100:
        return Response({
            'code': 400,
            'message': 'question_ids 最多100项',
            'data': None,
            'trace_id': '',
        }, status=400)

    visible_questions = _visible_relation_questions(request, question)
    candidate_questions, _ = find_relation_candidates(question, visible_questions)
    candidate_ids = {candidate.id for candidate in candidate_questions}

    created_count = 0
    existing_count = 0
    invalid_question_ids = []
    with transaction.atomic():
        for raw_question_id in unique_question_ids:
            raw_value = str(raw_question_id)
            try:
                related = ExamQuestion.objects.select_related('paper').get(pk=raw_question_id)
            except (ExamQuestion.DoesNotExist, ValidationError, ValueError, TypeError):
                invalid_question_ids.append(raw_value)
                continue
            if related.id == question.id or _teacher_question_scope_error(request, related):
                invalid_question_ids.append(raw_value)
                continue
            if not visible_questions.filter(pk=related.pk).exists():
                invalid_question_ids.append(raw_value)
                continue
            left, right = canonical_question_pair(question, related)
            if QuestionRelation.objects.filter(question_left=left, question_right=right).exists():
                existing_count += 1
                continue
            if related.id not in candidate_ids:
                invalid_question_ids.append(raw_value)
                continue
            _, created = QuestionRelation.objects.get_or_create(
                question_left=left,
                question_right=right,
                defaults={'created_by': request.user},
            )
            if created:
                created_count += 1
            else:
                existing_count += 1
    return _relation_response({
        'created_count': created_count,
        'existing_count': existing_count,
        'invalid_question_ids': invalid_question_ids,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_relation_candidates(request, question_id):
    question, error = _get_visible_question(request, question_id)
    if error:
        return error
    pagination, page_error = _relation_pagination(request)
    if page_error:
        return page_error
    page, page_size = pagination
    candidates, reason = find_relation_candidates(
        question,
        _visible_relation_questions(request, question),
    )
    sorted_candidates = sorted(candidates, key=lambda candidate: (candidate.sort_order, str(candidate.id)))
    total = len(sorted_candidates)
    start = (page - 1) * page_size
    page_candidates = sorted_candidates[start:start + page_size]
    displays = _relation_knowledge_points_display(page_candidates)
    items = [
        _relation_item(
            candidate,
            _common_knowledge_point_names(question, candidate),
            displays[candidate.id],
        )
        for candidate in page_candidates
    ]
    page_data = _relation_page_data(total, page, page_size, items)
    if reason:
        page_data['reason'] = reason
    return _relation_response(page_data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def question_relation_detail(request, question_id, related_id):
    manager_error = _question_bank_manager_error(request)
    if manager_error:
        return manager_error
    question, related, error = _get_visible_question_pair(request, question_id, related_id)
    if error:
        return error
    left, right = canonical_question_pair(question, related)
    removed, _ = QuestionRelation.objects.filter(question_left=left, question_right=right).delete()
    return _relation_response({'removed': bool(removed)})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def question_detail(request, question_id):
    """Q-07 / Q-08: Question detail / update."""
    try:
        q = ExamQuestion.objects.select_related('paper').get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response(
            {'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': ''},
            status=404
        )

    scope_error = _teacher_question_scope_error(request, q)
    if scope_error:
        return scope_error

    if request.method == 'GET':
        return Response({
            'code': 0, 'message': 'success',
            'data': QuestionDetailSerializer(q).data,
            'trace_id': ''
        })

    # PUT: update editable fields
    editable = ['ai_answer_a', 'ai_answer_b', 'ai_answer_c',
                'difficulty', 'subject', 'review_status',
                'stem', 'stem_html', 'answer', 'analysis', 'solution',
                'knowledge_points', 'tags', 'need_review', 'formula_need_review']
    if get_request_role(request) == 'teacher' and 'subject' in request.data:
        try:
            resolve_teacher_question_scope(
                request,
                requested_subject=request.data.get('subject') or '',
            )
        except TeachingScopeForbidden:
            return Response({
                'code': 'TEACHING_SCOPE_FORBIDDEN',
                'message': 'Subject is outside the teacher teaching scope.',
                'data': None,
                'trace_id': '',
            }, status=403)
    for field in editable:
        if field in request.data:
            setattr(q, field, request.data[field])
    q.save()
    return Response({'code': 0, 'message': '更新成功', 'data': None, 'trace_id': ''})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def question_publish(request, question_id):
    """Q-09: Publish (confirm) a question."""
    try:
        q = ExamQuestion.objects.get(pk=question_id)
        scope_error = _teacher_question_scope_error(request, q)
        if scope_error:
            return scope_error
        q.review_status = 'confirmed'
        q.need_review = False
        q.save()
        return Response({'code': 0, 'message': '发布成功', 'data': None, 'trace_id': ''})
    except ExamQuestion.DoesNotExist:
        return Response(
            {'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': ''},
            status=404
        )
