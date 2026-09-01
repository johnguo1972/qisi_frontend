"""Wrong book API views: S-09/S-10/S-11 + mastery records."""
import uuid
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudentOrParentContext
from rest_framework.response import Response
from .models import WrongBookItem, MasteryRecord
from .serializers import WrongBookItemSerializer, WrongBookDetailSerializer, MasteryRecordSerializer
from .services import find_variant_questions


def make_trace_id():
    return uuid.uuid4().hex[:16]


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOrParentContext])
def wrongbook_list(request):
    """S-09: Wrong book list."""
    student = getattr(request, '_effective_student', request.user)
    status_filter = request.GET.get('status')
    subject_filter = request.GET.get('subject', '').strip()
    class_filter = request.GET.get('class_id', '').strip()
    qs = WrongBookItem.objects.filter(student_user_id=student)
    if status_filter:
        qs = qs.filter(status=status_filter)

    if subject_filter:
        from apps.common.subject_codes import normalize_subject_code
        subject_aliases = {
            'math': ('math', '数学', 'M'),
            'physics': ('physics', '物理', 'P'),
            'chinese': ('chinese', '语文', 'CNL'),
            'english': ('english', '英语', 'E'),
            'chemistry': ('chemistry', '化学', 'C'),
            'biology': ('biology', '生物', 'B'),
            'geography': ('geography', '地理', 'G'),
            'history': ('history', '历史', 'H'),
        }
        subject_code = normalize_subject_code(subject_filter) or subject_filter.lower()
        values = subject_aliases.get(subject_code, (subject_filter,))
        from apps.parser.models import ExamQuestion
        question_ids = ExamQuestion.objects.filter(
            Q(subject__in=values) | Q(paper__subject__in=values)
        ).values('id')
        qs = qs.filter(question_id__in=question_ids)

    if class_filter:
        from apps.institutions.models import ClassStudent
        from apps.missions.models import LearningMission, TeacherWrongBookCell
        from apps.study.models import AnswerAttempt
        try:
            class_uuid = uuid.UUID(class_filter)
        except (ValueError, TypeError, AttributeError):
            return Response({
                'code': 400, 'message': 'class_id 无效', 'data': None,
                'trace_id': make_trace_id(),
            }, status=400)

        is_member = ClassStudent.objects.filter(
            class_obj_id=class_uuid, student=student, status='active',
        ).exists()
        if not is_member:
            qs = qs.none()
        else:
            mission_ids = LearningMission.objects.filter(
                Q(class_obj_id=class_uuid)
                | Q(class_assignments__class_obj_id=class_uuid, class_assignments__status='active')
            ).values('id')
            attempted_question_ids = AnswerAttempt.objects.filter(
                student_user_id=student, mission_id__in=mission_ids,
            ).exclude(submit_source='draft').values('question_id')
            matrix_item_ids = TeacherWrongBookCell.objects.filter(
                student=student, matrix__class_obj_id=class_uuid,
            ).values('wrong_book_item_id')
            qs = qs.filter(
                Q(question_id__in=attempted_question_ids) | Q(id__in=matrix_item_ids)
            )

    qs = qs.order_by('-latest_wrong_at')

    # The database has a unique (student, question) constraint. Keep this
    # defensive layer for legacy/imported rows so the client always receives
    # one card per question, preferring the newest record.
    serialized = WrongBookItemSerializer(qs, many=True).data
    deduplicated = []
    seen_question_ids = set()
    for item in serialized:
        question_id = str(item.get('question_id') or '')
        if question_id in seen_question_ids:
            continue
        seen_question_ids.add(question_id)
        deduplicated.append(item)

    return Response({
        'code': 0, 'message': 'success',
        'data': deduplicated,
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOrParentContext])
def wrongbook_detail(request, item_id):
    """S-10: Wrong book item detail."""
    try:
        item = WrongBookItem.objects.get(pk=item_id, student_user_id=request.user)
    except WrongBookItem.DoesNotExist:
        return Response({
            'code': 404, 'message': '错题不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)

    return Response({
        'code': 0, 'message': 'success',
        'data': WrongBookDetailSerializer(item).data,
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOrParentContext])
def wrongbook_variants(request, item_id):
    """S-11: Find variant questions for practice."""
    try:
        item = WrongBookItem.objects.get(pk=item_id, student_user_id=request.user)
    except WrongBookItem.DoesNotExist:
        return Response({
            'code': 404, 'message': '错题不存在', 'data': None,
            'trace_id': make_trace_id(),
        }, status=404)

    variants = find_variant_questions(item.question_id, limit=3)
    return Response({
        'code': 0, 'message': 'success',
        'data': variants,
        'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOrParentContext])
def mastery_list(request):
    """List mastery records for the current student."""
    records = MasteryRecord.objects.filter(
        student_user_id=request.user
    ).order_by('-updated_at')
    return Response({
        'code': 0, 'message': 'success',
        'data': MasteryRecordSerializer(records, many=True).data,
        'trace_id': make_trace_id(),
    })
