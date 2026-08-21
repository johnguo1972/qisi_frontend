"""Views for the personal practice domain."""
import uuid

from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.wrongbook.models import WrongBookItem
from apps.accounts.auth import get_request_role
from apps.parser.models import ExamQuestion
from .models import PracticeAttempt, PracticePoolItem, PracticeSet
from .online_services import submit_online_attempt
from .photo_services import (
    create_photo_attempt,
    serialize_photo_image,
    submit_photo_attempt,
    upload_photo,
)
from .permissions import IsPracticeStudentOnly, IsPracticeStudentOrParentContext
from .pdf_service import (
    ensure_practice_pdf,
    generate_practice_pdf,
    practice_pdf_download_url,
)
from .recommendation import QuestionBankWrongbookCandidateProvider
from .feature_flags import practice_feature_state
from .observability import log_practice_event
from .serializers import serialize_pool_item, serialize_set
from .services import (
    PracticeValidationError,
    activate_practice_set,
    add_pool_items,
    batch_remove_pool_items,
    create_practice_set,
    refresh_set_progress,
    remove_pool_item,
    submit_practice_set,
)


def make_trace_id():
    return uuid.uuid4().hex[:16]


@api_view(['GET'])
@permission_classes([AllowAny])
def practice_health(request):
    """Minimal readiness endpoint for deployment probes."""
    from django.db import connection
    from django.db.migrations.recorder import MigrationRecorder

    required_tables = {
        'practice_pool_item', 'practice_set', 'practice_set_item',
        'practice_attempt', 'practice_attempt_image',
    }
    try:
        tables = set(connection.introspection.table_names())
        migration_ready = MigrationRecorder(connection).migration_qs.filter(
            app='practice', name='0001_initial',
        ).exists()
    except Exception as error:
        log_practice_event('health_check_failed', level=40, error=type(error).__name__)
        tables = set()
        migration_ready = False
    database_ready = required_tables.issubset(tables)
    ready = migration_ready and database_ready
    return Response({
        'code': 0 if ready else 503,
        'message': 'ready' if ready else 'practice migration or tables are not ready',
        'data': {
            'status': 'ready' if ready else 'not_ready',
            'migration_ready': migration_ready,
            'database_ready': database_ready,
            'feature': practice_feature_state(),
        },
        'trace_id': make_trace_id(),
    }, status=200 if ready else 503)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def wrongbook_candidates(request, wrong_item_id):
    """Return strict candidates for adding to the effective student's pool."""
    student = getattr(request, '_effective_student', None)
    item = WrongBookItem.objects.filter(
        pk=wrong_item_id,
        student_user_id=student,
    ).first()
    # 兼容旧版小程序曾把 question_id 直接拼到候选题路由中的情况。
    # 仍然限定当前有效学生，不能借此访问其他学生的错题。
    if item is None:
        item = WrongBookItem.objects.filter(
            question_id=wrong_item_id,
            student_user_id=student,
        ).first()
    if item is None:
        return Response({
            'code': 404,
            'message': '错题不存在',
            'data': [],
            'meta': None,
            'trace_id': make_trace_id(),
        }, status=404)

    result = QuestionBankWrongbookCandidateProvider().recommend_for_wrong_item(
        student=student,
        wrong_item=item,
        limit=3,
    )
    if len(result['items']) < 3:
        log_practice_event(
            'recommendation_insufficient', level=30,
            wrong_item_id=str(item.id), returned_count=len(result['items']),
            reason_codes=result['meta'].get('reason_codes'),
        )
    return Response({
        'code': 0,
        'message': 'success',
        'data': result['items'],
        'meta': result['meta'],
        'trace_id': make_trace_id(),
    })


def _validation_error_response(error):
    data = {'error_code': error.code, 'message': error.message}
    if error.item_index is not None:
        data['item_index'] = error.item_index
    return Response({
        'code': 400,
        'message': error.message,
        'data': data,
        'trace_id': make_trace_id(),
    }, status=400)


def _effective_student(request):
    return getattr(request, '_effective_student', None)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def pool_list(request):
    student = _effective_student(request)
    status = request.GET.get('status', 'active')
    if status not in {'active', 'removed', 'all'}:
        return Response({
            'code': 400, 'message': 'status 参数不正确', 'data': None,
            'trace_id': make_trace_id(),
        }, status=400)
    queryset = PracticePoolItem.objects.filter(student_user=student)
    if status != 'all':
        queryset = queryset.filter(status=status)
    queryset = queryset.order_by('-created_at')
    return Response({
        'code': 0,
        'message': 'success',
        'data': [serialize_pool_item(item) for item in queryset],
        'meta': {'status': status, 'count': queryset.count()},
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def pool_items_create(request):
    try:
        results = add_pool_items(
            student=_effective_student(request),
            items=request.data.get('items'),
        )
    except PracticeValidationError as error:
        return _validation_error_response(error)
    data = [
        {'status': result['status'], 'item': serialize_pool_item(result['item'])}
        for result in results
    ]
    return Response({
        'code': 0,
        'message': 'success',
        'data': data,
        'meta': {
            'added_count': sum(result['status'] == 'added' for result in results),
            'restored_count': sum(result['status'] == 'restored' for result in results),
            'already_exists_count': sum(result['status'] == 'already_exists' for result in results),
        },
        'trace_id': make_trace_id(),
    }, status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def pool_item_remove(request, item_id):
    try:
        item, status = remove_pool_item(student=_effective_student(request), item_id=item_id)
    except PracticeValidationError as error:
        return _validation_error_response(error)
    return Response({
        'code': 0,
        'message': 'success',
        'data': {'status': status, 'item': serialize_pool_item(item)},
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def pool_items_batch_remove(request):
    try:
        items, changed = batch_remove_pool_items(
            student=_effective_student(request),
            item_ids=request.data.get('item_ids'),
        )
    except PracticeValidationError as error:
        return _validation_error_response(error)
    return Response({
        'code': 0,
        'message': 'success',
        'data': [serialize_pool_item(item) for item in items],
        'meta': {'removed_count': len(changed), 'requested_count': len(items)},
        'trace_id': make_trace_id(),
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def practice_set_list(request):
    if request.method == 'POST':
        try:
            practice_set = create_practice_set(
                request=request,
                student=_effective_student(request),
                title=request.data.get('title'),
                pool_item_ids=request.data.get('pool_item_ids'),
                status=request.data.get('status', 'draft'),
            )
        except PracticeValidationError as error:
            return _validation_error_response(error)
        return Response({
            'code': 0,
            'message': 'success',
            'data': serialize_set(practice_set, include_items=True),
            'trace_id': make_trace_id(),
        }, status=201)
    student = _effective_student(request)
    status = request.GET.get('status')
    queryset = PracticeSet.objects.filter(student_user=student)
    if status:
        if status not in {'draft', 'active', 'completed', 'archived'}:
            return Response({
                'code': 400, 'message': 'status 参数不正确', 'data': None,
                'trace_id': make_trace_id(),
            }, status=400)
        queryset = queryset.filter(status=status)
    queryset = queryset.order_by('-updated_at')
    return Response({
        'code': 0,
        'message': 'success',
        'data': [serialize_set(item) for item in queryset],
        'meta': {'count': queryset.count()},
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def practice_set_create(request):
    try:
        practice_set = create_practice_set(
            request=request,
            student=_effective_student(request),
            title=request.data.get('title'),
            pool_item_ids=request.data.get('pool_item_ids'),
            status=request.data.get('status', 'draft'),
        )
    except PracticeValidationError as error:
        return _validation_error_response(error)
    return Response({
        'code': 0,
        'message': 'success',
        'data': serialize_set(practice_set, include_items=True),
        'trace_id': make_trace_id(),
    }, status=201)


def _owned_set(request, set_id):
    return PracticeSet.objects.filter(
        pk=set_id, student_user=_effective_student(request),
    ).first()


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def practice_set_detail(request, set_id):
    practice_set = _owned_set(request, set_id)
    if practice_set is None:
        return Response({
            'code': 404, 'message': '精练作业不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)
    refresh_set_progress(practice_set)
    return Response({
        'code': 0, 'message': 'success',
        'data': serialize_set(practice_set, include_items=True),
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def practice_set_activate(request, set_id):
    practice_set = _owned_set(request, set_id)
    if practice_set is None:
        return Response({
            'code': 404, 'message': '精练作业不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)
    try:
        practice_set = activate_practice_set(practice_set=practice_set)
    except PracticeValidationError as error:
        return _validation_error_response(error)
    return Response({
        'code': 0, 'message': 'success',
        'data': serialize_set(practice_set),
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def practice_set_submit(request, set_id):
    practice_set = _owned_set(request, set_id)
    if practice_set is None:
        return Response({
            'code': 404, 'message': '精练作业不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)
    try:
        practice_set = submit_practice_set(practice_set=practice_set)
    except PracticeValidationError as error:
        return _validation_error_response(error)
    return Response({
        'code': 0, 'message': 'success',
        'data': serialize_set(practice_set),
        'trace_id': make_trace_id(),
    })


def _practice_set_item_payload(item, *, include_images=True):
    from .serializers import serialize_set_item

    payload = serialize_set_item(item)
    latest = item.attempts.order_by('-attempt_no', '-created_at').first()
    payload['attempted'] = latest is not None
    payload['attempt_count'] = item.attempts.count()
    if latest is not None:
        question = ExamQuestion.objects.filter(pk=item.question_id).only(
            'answer', 'analysis', 'solution', 'raw_explanation'
        ).first()
        payload['latest_attempt'] = {
            'id': str(latest.id),
            'status': latest.status,
            'is_correct': latest.is_correct,
            'is_subjective_pending': latest.is_subjective_pending,
            'score': float(latest.score) if latest.score is not None else None,
            'student_answer': latest.answer_content,
            'correct_answer': question.answer if question else '',
            'analysis': (
                (question.analysis or question.solution or question.raw_explanation)
                if question else ''
            ),
            'submitted_at': latest.submitted_at,
            'images': [serialize_photo_image(image) for image in latest.images.all().order_by('page_no')] if include_images else [],
        }
    else:
        payload['latest_attempt'] = None
    return payload


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def practice_set_questions(request, set_id):
    practice_set = _owned_set(request, set_id)
    if practice_set is None:
        return Response({
            'code': 404, 'message': '精练作业不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)
    items = practice_set.items.all().order_by('sort_no', 'id')
    return Response({
        'code': 0,
        'message': 'success',
        'data': [
            _practice_set_item_payload(
                item,
                include_images=get_request_role(request) == 'student',
            )
            for item in items
        ],
        'meta': {'set_id': str(practice_set.id), 'question_count': practice_set.question_count},
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOnly])
def practice_attempt_submit(request, set_id, set_item_id):
    try:
        practice_set, set_item, attempt = submit_online_attempt(
            student=_effective_student(request),
            set_id=set_id,
            set_item_id=set_item_id,
            question_id=request.data.get('question_id'),
            answer_content=request.data.get('answer_content'),
        )
    except PracticeValidationError as error:
        return _validation_error_response(error)
    question = ExamQuestion.objects.filter(pk=set_item.question_id).only(
        'answer', 'analysis', 'solution', 'raw_explanation'
    ).first()
    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'attempt_id': str(attempt.id),
            'set_item_id': str(set_item.id),
            'is_correct': attempt.is_correct,
            'is_pending': attempt.is_subjective_pending,
            'score': float(attempt.score) if attempt.score is not None else None,
            'attempt_no': attempt.attempt_no,
            'status': attempt.status,
            'student_answer': attempt.answer_content,
            'correct_answer': question.answer if question else '',
            'analysis': (
                (question.analysis or question.solution or question.raw_explanation)
                if question else ''
            ),
            'answered_count': practice_set.answered_count,
            'question_count': practice_set.question_count,
            'progress_percent': float(practice_set.progress_percent),
        },
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOnly])
def practice_photo_attempt_draft(request, set_id, set_item_id):
    try:
        practice_set, set_item, attempt = create_photo_attempt(
            student=_effective_student(request),
            set_id=set_id,
            set_item_id=set_item_id,
            question_id=request.data.get('question_id'),
        )
    except PracticeValidationError as error:
        log_practice_event('photo_draft_rejected', level=30, set_id=str(set_id), set_item_id=str(set_item_id), error_code=error.code)
        return _validation_error_response(error)
    return Response({
        'code': 0,
        'message': '草稿已创建',
        'data': {
            'attempt_id': str(attempt.id),
            'set_id': str(practice_set.id),
            'set_item_id': str(set_item.id),
            'attempt_no': attempt.attempt_no,
            'status': attempt.status,
            'images': [],
        },
        'trace_id': make_trace_id(),
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOnly])
def practice_photo_image_upload(request, attempt_id):
    try:
        attempt, image = upload_photo(
            student=_effective_student(request),
            attempt_id=attempt_id,
            image=request.FILES.get('image'),
            page_no=request.data.get('page_no') or 1,
        )
    except PracticeValidationError as error:
        log_practice_event('photo_upload_rejected', level=30, attempt_id=str(attempt_id), error_code=error.code)
        return _validation_error_response(error)
    return Response({
        'code': 0,
        'message': '上传成功',
        'data': {
            'attempt_id': str(attempt.id),
            'image': serialize_photo_image(image),
            'image_count': attempt.images.count(),
        },
        'trace_id': make_trace_id(),
    }, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOnly])
def practice_photo_attempt_submit(request, attempt_id):
    try:
        practice_set, set_item, attempt = submit_photo_attempt(
            student=_effective_student(request),
            attempt_id=attempt_id,
            answer_content=request.data.get('answer_content'),
        )
    except PracticeValidationError as error:
        log_practice_event('photo_submit_rejected', level=30, attempt_id=str(attempt_id), error_code=error.code)
        return _validation_error_response(error)
    return Response({
        'code': 0,
        'message': '已提交，等待批阅',
        'data': {
            'attempt_id': str(attempt.id),
            'set_id': str(practice_set.id),
            'set_item_id': str(set_item.id),
            'status': attempt.status,
            'is_pending': attempt.is_subjective_pending,
            'submitted_at': attempt.submitted_at,
            'progress_percent': float(practice_set.progress_percent),
        },
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def practice_set_progress(request, set_id):
    practice_set = _owned_set(request, set_id)
    if practice_set is None:
        return Response({
            'code': 404, 'message': '精练作业不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)
    from .serializers import serialize_set_item

    from .services import refresh_set_progress
    refresh_set_progress(practice_set)
    items = []
    for item in practice_set.items.all().order_by('sort_no', 'id'):
        latest = item.attempts.order_by('-attempt_no', '-created_at').first()
        items.append({
            'set_item_id': str(item.id),
            'sort_no': item.sort_no,
            'question_id': str(item.question_id),
            'attempted': latest is not None,
            'status': latest.status if latest else 'not_started',
            'is_correct': latest.is_correct if latest else None,
            'is_subjective_pending': latest.is_subjective_pending if latest else False,
        })
    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'set': serialize_set(practice_set),
            'items': items,
        },
        'trace_id': make_trace_id(),
    })


def _practice_pdf_rate_allowed(actor_id):
    key = f'practice_pdf_rate:{actor_id}'
    count = cache.get(key, 0)
    if count >= 3:
        return False
    cache.set(key, count + 1, 3600)
    return True


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def practice_set_export_pdf(request, set_id):
    practice_set = _owned_set(request, set_id)
    if practice_set is None:
        return Response({
            'code': 404, 'message': '精练作业不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)
    if not _practice_pdf_rate_allowed(request.user.id):
        return Response({
            'code': 429, 'message': 'PDF 导出过于频繁，请稍后再试', 'data': None,
            'trace_id': make_trace_id(),
        }, status=429)
    include_answers = _as_bool(request.data.get('include_answers', False))
    if include_answers and get_request_role(request) != 'student':
        return Response({
            'code': 403, 'message': '当前身份不能生成答案卷', 'data': None,
            'trace_id': make_trace_id(),
        }, status=403)
    watermark_text = str(request.data.get('watermark_text') or '')[:100]
    try:
        relative_path = generate_practice_pdf(
            practice_set,
            include_answers=include_answers,
            watermark_text=watermark_text,
        )
    except (OSError, ValueError) as error:
        log_practice_event('pdf_generation_failed', level=40, set_id=str(set_id), error=str(error))
        return Response({
            'code': 500, 'message': f'PDF 生成失败：{error}', 'data': None,
            'trace_id': make_trace_id(),
        }, status=500)
    return Response({
        'code': 0,
        'message': '导出成功',
        'data': {
            'download_url': practice_pdf_download_url(relative_path),
            'pdf_file_path': relative_path,
            'question_count': practice_set.question_count,
            'pdf_version': practice_set.pdf_version,
        },
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsPracticeStudentOrParentContext])
def practice_set_pdf(request, set_id):
    practice_set = _owned_set(request, set_id)
    if practice_set is None:
        return Response({
            'code': 404, 'message': '精练作业不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)
    try:
        relative_path = ensure_practice_pdf(practice_set)
    except (OSError, ValueError) as error:
        log_practice_event('pdf_generation_failed', level=40, set_id=str(set_id), error=str(error))
        return Response({
            'code': 500, 'message': f'PDF 生成失败：{error}', 'data': None,
            'trace_id': make_trace_id(),
        }, status=500)
    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'download_url': practice_pdf_download_url(relative_path),
            'pdf_file_path': relative_path,
            'pdf_version': practice_set.pdf_version,
        },
        'trace_id': make_trace_id(),
    })
