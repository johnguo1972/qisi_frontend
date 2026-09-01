import uuid
import json
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.accounts.permissions import IsTeacherSession
from .models import LearningMission, MissionLevel, MissionQuestionRel, MissionClassAssignment
from apps.study.models import AnswerAttempt
from apps.institutions.models import ClassStudent
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption
from apps.common.ai.components import GuidanceComponent, GuidanceContext
from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.media import media_url
from .serializers import (
    MissionListSerializer, MissionDetailSerializer,
    CreateMissionSerializer, CreateLevelSerializer, AddQuestionsSerializer,
    BatchCreateLevelsSerializer, subject_filter_values,
    FlatQuestionsSerializer,
)
from .services import (
    FLAT_ASSIGNMENT_MODE,
    assignment_levels,
    class_grade_in_teacher_scope,
    close_stale_missions,
    ensure_flat_assignment_level,
    ordered_mission_question_rels,
    question_no_sort_key,
)
from .pdf_service import ensure_mission_pdf, mission_pdf_download_url
from .snapshots import apply_snapshot_to_question, snapshot_payload


def make_trace_id():
    return uuid.uuid4().hex[:16]


def _mission_assignments(mission, active_only=True):
    """Return new class assignments, falling back to the legacy class field."""
    query = mission.class_assignments.filter(status='active') if active_only else mission.class_assignments.all()
    assignments = list(query.select_related('class_obj'))
    if assignments:
        return assignments
    return [mission] if mission.class_obj_id else []


def _managed_class_ids(user):
    from apps.institutions.models import ClassTeacher, Class
    return set(ClassTeacher.objects.filter(teacher=user).values_list('class_obj_id', flat=True)) | set(
        Class.objects.filter(creator_teacher=user).values_list('id', flat=True)
    )


def _validate_mission_classes(user, class_ids, course=None):
    from apps.institutions.models import Class
    ids = list(dict.fromkeys(str(value) for value in (class_ids or []) if value))
    classes = list(Class.objects.filter(pk__in=ids, status='active'))
    if len(classes) != len(ids):
        return None, '存在无效或已停用的班级'
    managed = {str(value) for value in _managed_class_ids(user)}
    if any(str(cls.id) not in managed for cls in classes):
        return None, '只能选择自己管理的班级'
    if course and course.institution_id and any(cls.institution_id != course.institution_id for cls in classes):
        return None, '班级与课程所属机构不一致'
    if any(not class_grade_in_teacher_scope(cls, user) for cls in classes):
        return None, '所选班级年级超出教师任教范围'
    return classes, None


def _mission_student_ids(mission, class_id=None):
    """Return active students assigned to the mission, honoring per-class targets."""
    from apps.institutions.models import ClassStudent
    from apps.accounts.models import UserAccount

    targets = {str(student_id) for student_id in (mission.target_student_ids or [])}
    assignments = _mission_assignments(mission)
    if class_id:
        assignments = [item for item in assignments if str(getattr(item, 'class_obj_id', '')) == str(class_id)]
        if not assignments:
            return UserAccount.objects.none().values_list('id', flat=True)
    if not assignments:
        if not targets:
            return UserAccount.objects.none().values_list('id', flat=True)
        return UserAccount.objects.filter(
            id__in=targets,
            status='active',
        ).filter(
            Q(role_type='student') |
            Q(role_grants__role='student', role_grants__status='active'),
        ).distinct().values_list('id', flat=True)

    student_ids = set()
    for assignment in assignments:
        class_id = getattr(assignment, 'class_obj_id', None)
        class_targets = {str(value) for value in (getattr(assignment, 'target_student_ids', None) or [])}
        query = ClassStudent.objects.filter(class_obj_id=class_id, status='active')
        effective_targets = class_targets or targets
        if effective_targets:
            query = query.filter(student_id__in=effective_targets)
        student_ids.update(str(value) for value in query.values_list('student_id', flat=True))
    return UserAccount.objects.filter(id__in=student_ids, status='active').values_list('id', flat=True)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_add_favorites(request, mission_id):
    """Add the teacher's selected favorite questions to a mission."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': 'mission not found'}, status=404)
    question_ids = request.data.get('question_ids') or []
    if not isinstance(question_ids, list) or not question_ids:
        return Response({'code': 400, 'message': 'question_ids required'}, status=400)
    from apps.study.models import Favorite
    allowed = set(Favorite.objects.filter(user=request.user, question_id__in=question_ids)
                  .values_list('question_id', flat=True))
    level = mission.levels.order_by('level_no').first()
    if level is None:
        level = MissionLevel.objects.create(
            mission=mission, level_no=1, level_name='精选题目',
            level_type='practice', mode_policy=mission.default_mode_policy or 'free_practice',
        )
    existing = set(MissionQuestionRel.objects.filter(mission=mission).values_list('question_id', flat=True))
    added = 0
    for question_id in allowed - existing:
        MissionQuestionRel.objects.create(
            mission=mission, level=level, question_id=question_id,
            sort_no=MissionQuestionRel.objects.filter(level=level).count(),
            source_type='favorite',
        )
        added += 1
    return Response({'code': 0, 'message': 'success', 'data': {'added': added}})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_export_pdf(request, mission_id):
    """Export a teacher-owned mission as a downloadable PDF."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': 'mission not found'}, status=404)
    try:
        ensure_mission_pdf(mission)
    except ImportError:
        return Response({'code': 503, 'message': 'PDF dependency unavailable'}, status=503)
    except ValueError as exc:
        return Response({'code': 404, 'message': str(exc)}, status=404)
    return Response({'code': 0, 'data': {'download_url': mission_pdf_download_url(mission)}})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_grading(request, mission_id):
    """Return teacher-facing student submissions for a mission."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': 'mission not found'}, status=404)
    student_ids = list(_mission_student_ids(mission))
    from apps.accounts.models import UserAccount
    students = UserAccount.objects.filter(id__in=student_ids, status='active').order_by('display_name', 'mobile')
    attempts = AnswerAttempt.objects.filter(mission=mission, student_user_id__in=student_ids).order_by('student_user_id', '-submitted_at')
    question_ids = {str(attempt.question_id) for attempt in attempts}
    question_map = {
        str(question.id): question for question in ExamQuestion.objects.filter(id__in=question_ids)
        .prefetch_related('options', 'images')
    }
    relations = ordered_mission_question_rels(mission)
    relation_map = {
        (str(relation.question_id), str(relation.level_id) if relation.level_id else ''): relation
        for relation in relations
    }
    fallback_relations = {}
    for relation in relations:
        fallback_relations.setdefault(str(relation.question_id), relation)
    attempt_rows = []
    for attempt in attempts:
        question = question_map.get(str(attempt.question_id))
        relation = relation_map.get(
            (str(attempt.question_id), str(attempt.level_id) if attempt.level_id else ''),
        ) or fallback_relations.get(str(attempt.question_id))
        display_question = apply_snapshot_to_question(question, relation) if question else None
        display_payload = snapshot_payload(question, relation) if question else {}
        attempt_rows.append({
            'id': str(attempt.id),
            'student_id': str(attempt.student_user_id_id),
            'question_id': str(attempt.question_id),
            'level_id': str(attempt.level_id) if attempt.level_id else '',
            'question_no': display_payload.get('question_no') or getattr(display_question, 'question_no', ''),
            'question_type': display_payload.get('question_type') or getattr(display_question, 'question_type', ''),
            'stem': display_payload.get('stem') or getattr(display_question, 'stem', ''),
            'stem_html': display_payload.get('stem_html') or getattr(display_question, 'stem_html', ''),
            'options': display_payload.get('options') or [],
            'correct_answer': (
                display_payload.get('answer')
                or getattr(display_question, 'answer', '')
                or ((getattr(display_question, 'ai_answer_a', None) or {}).get('answer', '') if display_question else '')
                or ''
            ),
            'analysis': display_payload.get('analysis') or getattr(display_question, 'analysis', '') or '',
            'solution': display_payload.get('solution') or getattr(display_question, 'solution', '') or '',
            'images': display_payload.get('images') or [],
            'answer_content': attempt.answer_content,
            'is_correct': attempt.is_correct,
            'is_subjective_pending': attempt.is_subjective_pending,
            'score': float(attempt.score),
            'submitted_at': attempt.submitted_at,
        })
    return Response({'code': 0, 'data': {
        'students': [{
            'id': str(student.id), 'name': student.display_name, 'mobile': student.mobile,
        } for student in students],
        'attempts': attempt_rows,
    }})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_progress(request, mission_id):
    """Return progress using the latest valid attempt for each required question."""
    from apps.accounts.models import UserAccount
    from apps.study.models import StudentMissionProgress

    try:
        mission = LearningMission.objects.select_related('class_obj').get(
            pk=mission_id, creator_teacher_id=request.user,
        )
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': 'mission not found'}, status=404)

    class_id = request.GET.get('class_id', '').strip()
    all_assignments = _mission_assignments(mission)
    if class_id and not any(str(item.class_obj_id) == class_id for item in all_assignments):
        return Response({'code': 404, 'message': '班级任务不存在', 'data': None}, status=404)
    assignments = [item for item in all_assignments if not class_id or str(item.class_obj_id) == class_id]
    student_ids = list(_mission_student_ids(mission, class_id=class_id or None))
    students = UserAccount.objects.filter(id__in=student_ids, status='active').order_by('display_name', 'mobile')
    rels = [rel for rel in ordered_mission_question_rels(mission) if rel.is_required]
    # Legacy level-only records may not have flat relations. Preserve their
    # established progress contract while still returning every student.
    if not rels:
        progress_by_student = {
            str(progress.student_user_id_id): progress
            for progress in StudentMissionProgress.objects.filter(mission=mission, student_user_id__in=student_ids)
        }
        rows = []
        completed = 0
        for student in students:
            progress = progress_by_student.get(str(student.id))
            progress_status = progress.progress_status if progress else 'not_started'
            progress_percent = float(progress.progress_percent) if progress else 0.0
            if progress_status in ('completed', 'passed'):
                completed += 1
            rows.append({
                'student_id': str(student.id), 'student_name': student.display_name or student.mobile,
                'mobile': student.mobile, 'progress_status': progress_status,
                'progress_percent': progress_percent, 'last_action_at': progress.last_action_at if progress else None,
            })
        total = len(rows)
        return Response({'code': 0, 'data': {
            'mission_id': str(mission.id), 'mission_name': mission.mission_name,
            'mission_status': mission.status,
            'class_id': class_id or None,
            'class_name': '、'.join(item.class_obj.class_name for item in assignments if getattr(item, 'class_obj', None)) or None,
            'summary': {'completed': completed, 'total': total, 'unfinished': max(total - completed, 0), 'percent': round(completed / total * 100, 2) if total else 0},
            'students': rows,
        }})
    question_ids = {str(rel.question_id) for rel in rels}
    attempts = AnswerAttempt.objects.filter(
        mission=mission, student_user_id__in=student_ids, question_id__in=question_ids,
    ).exclude(submit_source='draft').order_by('student_user_id', 'question_id', '-submitted_at', '-attempt_no')
    latest = {}
    for attempt in attempts:
        key = (str(attempt.student_user_id_id), str(attempt.question_id))
        latest.setdefault(key, attempt)
    progress_by_student = {
        str(progress.student_user_id_id): progress
        for progress in StudentMissionProgress.objects.filter(mission=mission, student_user_id__in=student_ids)
    }
    now = timezone.now()
    end_at = mission.end_at
    rows = []
    counts = {'not_started': 0, 'in_progress': 0, 'submitted': 0, 'graded': 0}
    for student in students:
        sid = str(student.id)
        student_attempts = [attempt for (student_key, _), attempt in latest.items() if student_key == sid]
        answered_count = len(student_attempts)
        submitted_count = sum(1 for attempt in student_attempts if attempt.submit_source != 'draft')
        subjective_pending = sum(1 for attempt in student_attempts if attempt.is_subjective_pending)
        correct_count = sum(1 for attempt in student_attempts if attempt.is_correct and not attempt.is_subjective_pending)
        objective_count = submitted_count - subjective_pending
        question_count = len(rels)
        percent = round(submitted_count / question_count * 100, 2) if question_count else 0
        if submitted_count == 0:
            base_status = 'not_started'
        elif submitted_count >= question_count:
            base_status = 'submitted' if subjective_pending else 'graded'
        else:
            base_status = 'in_progress'
        overdue = bool(end_at and now > end_at and base_status not in ('graded', 'submitted'))
        progress = progress_by_student.get(sid)
        last_action = max((attempt.submitted_at for attempt in student_attempts), default=(progress.last_action_at if progress else None))
        counts[base_status] += 1
        rows.append({
            'student_id': sid,
            'student_name': student.display_name or student.mobile,
            'mobile': student.mobile,
            'status': base_status,
            'progress_status': base_status,
            'progress_percent': percent,
            'answered_count': answered_count,
            'question_count': question_count,
            'correct_count': correct_count,
            'accuracy': round(correct_count / objective_count * 100, 2) if objective_count else 0,
            'submitted_at': max((attempt.submitted_at for attempt in student_attempts), default=None),
            'graded_at': max((attempt.submitted_at for attempt in student_attempts if not attempt.is_subjective_pending), default=None) if subjective_pending == 0 and submitted_count else None,
            'last_action_at': last_action,
            'overdue': overdue,
        })
    status_filter = request.GET.get('status', '').strip()
    keyword = request.GET.get('keyword', '').strip().lower()
    if status_filter:
        rows = [row for row in rows if row['status'] == status_filter or (status_filter == 'overdue' and row['overdue'])]
    if keyword:
        rows = [row for row in rows if keyword in (row['student_name'] or '').lower() or keyword in (row['mobile'] or '')]
    total = len(students)
    visible_total = len(rows)
    graded = counts['graded']
    submitted = counts['submitted']
    return Response({'code': 0, 'data': {
        'mission_id': str(mission.id),
        'mission_name': mission.mission_name,
        'mission_status': mission.status,
        'class_id': class_id or None,
        'class_name': '、'.join(cls.class_name for item in assignments for cls in [item.class_obj] if cls) or None,
        'class_names': [item.class_obj.class_name for item in assignments if getattr(item, 'class_obj', None)],
        'summary': {
            'not_started': counts['not_started'],
            'in_progress': counts['in_progress'],
            'submitted': submitted,
            'graded': graded,
            'completed': graded,
            'total': total,
            'unfinished': max(total - graded - submitted, 0),
            'completion_rate': round((graded + submitted) / total * 100, 2) if total else 0,
            'percent': round((graded + submitted) / total * 100, 2) if total else 0,
        },
        'students': rows,
        'filters': {'status': status_filter or None, 'keyword': keyword or None},
        'total': visible_total,
    }})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_grade_attempt(request, mission_id, attempt_id):
    """Save a teacher's score and feedback for one subjective submission."""
    try:
        attempt = AnswerAttempt.objects.select_related('mission').get(
            pk=attempt_id, mission_id=mission_id, mission__creator_teacher_id=request.user,
        )
    except AnswerAttempt.DoesNotExist:
        return Response({'code': 404, 'message': 'attempt not found'}, status=404)
    try:
        score = float(request.data.get('score'))
    except (TypeError, ValueError):
        return Response({'code': 400, 'message': 'score must be a number'}, status=400)
    if not 0 <= score <= 100:
        return Response({'code': 400, 'message': 'score must be between 0 and 100'}, status=400)
    feedback = str(request.data.get('feedback') or '').strip()
    content = attempt.answer_content if isinstance(attempt.answer_content, dict) else {'answer': attempt.answer_content}
    if feedback:
        content['teacher_feedback'] = feedback
    attempt.answer_content = content
    attempt.score = score
    attempt.is_correct = score >= 60
    attempt.is_subjective_pending = False
    attempt.save(update_fields=['answer_content', 'score', 'is_correct', 'is_subjective_pending'])
    # Keep the grading endpoint decoupled from study imports at module load
    # time; the local import also avoids a missions/study circular import.
    from apps.study.answer_views import _update_mission_progress

    _update_mission_progress(attempt.mission, attempt.student_user_id, final=True)
    return Response({'code': 0, 'data': {'id': str(attempt.id), 'score': score, 'is_correct': attempt.is_correct}})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_generate_variant(request, mission_id):
    """Generate a variant from a submitted question for one student."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
        question_id = request.data.get('question_id')
        level_id = request.data.get('level_id')
        student_id = str(request.data.get('student_id') or '')
        variant_mode = str(request.data.get('variant_mode') or '情境变化')
        level = MissionLevel.objects.get(pk=level_id, mission=mission)
        if not question_id or not student_id:
            raise ValueError('question_id and student_id are required')
        allowed = ClassStudent.objects.filter(
            class_obj_id=mission.class_obj_id, student_id=student_id, status='active',
        ).exists()
        if not allowed or (mission.target_student_ids and student_id not in {str(v) for v in mission.target_student_ids}):
            return Response({'code': 400, 'message': 'student is not assigned to this mission'}, status=400)
        from apps.courses.views import generate_variant_task_dispatch
        task = generate_variant_task_dispatch(
            question_id=question_id, variant_mode=variant_mode,
            mission_id=str(mission.id), level_id=str(level.id), target_student_id=student_id,
        )
        return Response({'code': 0, 'data': {'task_id': task.id}})
    except (LearningMission.DoesNotExist, MissionLevel.DoesNotExist):
        return Response({'code': 404, 'message': 'mission or level not found'}, status=404)
    except ValueError as exc:
        return Response({'code': 400, 'message': str(exc)}, status=400)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_list(request):
    """M-01 / M-02: List / Create missions."""
    user = request.user

    if request.method == 'GET':
        close_stale_missions()
        missions = LearningMission.objects.filter(
            creator_teacher_id=user
        ).select_related('course', 'class_obj').prefetch_related('class_assignments__class_obj').order_by('-created_at')
        class_id = request.GET.get('class_id')
        if class_id:
            missions = missions.filter(Q(class_obj_id=class_id) | Q(class_assignments__class_obj_id=class_id)).distinct()
        subject = request.GET.get('subject', '').strip()
        if subject:
            subject_values = subject_filter_values(subject)
            question_ids = ExamQuestion.objects.filter(
                subject__in=subject_values,
            ).values_list('id', flat=True)
            mission_ids = MissionQuestionRel.objects.filter(
                question_id__in=question_ids,
            ).values_list('mission_id', flat=True)
            missions = missions.filter(
                Q(course__subject__in=subject_values) | Q(id__in=mission_ids),
            ).distinct()
        if request.GET.get('unfinished', '').lower() in ('1', 'true', 'yes'):
            from apps.study.models import StudentMissionProgress
            unfinished = StudentMissionProgress.objects.filter(
                mission_id=OuterRef('pk'),
            ).exclude(progress_status__in=('completed', 'passed'))
            missions = missions.filter(Q(status='draft') | Exists(unfinished))
        return Response({
            'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
            'data': MissionListSerializer(missions, many=True).data,
        })

    # POST: create
    serializer = CreateMissionSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    class_ids = request.data.get('class_ids')
    if class_ids is None and request.data.get('class_id'):
        class_ids = [request.data.get('class_id')]
    course = serializer.validated_data.get('course_id')
    if course:
        from apps.courses.models import Course
        course = Course.objects.filter(pk=course).first()
    classes, error = _validate_mission_classes(user, class_ids, course)
    if error:
        return Response({'code': 403, 'message': error, 'data': None, 'trace_id': make_trace_id()}, status=403)
    try:
        with transaction.atomic():
            mission = serializer.save(creator_teacher_id=user)
            # The serializer creates relations for the new class_ids contract.
            # Legacy class_id requests need the same relation for consistent reads.
            if classes and not mission.class_assignments.filter(status='active').exists():
                for cls in classes:
                    MissionClassAssignment.objects.create(
                        mission=mission, class_obj=cls,
                        start_at=mission.start_at, end_at=mission.end_at,
                        target_student_ids=list(mission.target_student_ids or []),
                    )
    except Exception:
        raise
    return Response({
        'code': 0, 'message': '创建成功',
        'data': {'id': mission.id, 'mission_no': mission.mission_no,
                 'class_ids': [str(cls.id) for cls in classes or []]},
        'trace_id': make_trace_id(),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_detail(request, mission_id):
    """M-03 / M-04: Mission detail / update."""
    close_stale_missions()
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response({
            'code': 0, 'message': 'success',
            'data': MissionDetailSerializer(mission).data, 'trace_id': make_trace_id(),
        })

    # PUT: update
    requested_class_ids = request.data.get('class_ids')
    if requested_class_ids is None and 'class_id' in request.data:
        requested_class_ids = [request.data.get('class_id')] if request.data.get('class_id') else []
    if requested_class_ids is not None:
        from apps.courses.models import Course
        course = Course.objects.filter(pk=request.data.get('course_id') or mission.course_id).first()
        classes, error = _validate_mission_classes(request.user, requested_class_ids, course)
        if error:
            return Response({'code': 403, 'message': error, 'data': None, 'trace_id': make_trace_id()}, status=403)
    else:
        classes = None
    for field in ['mission_name', 'goal_text', 'start_at', 'end_at', 'default_mode_policy', 'assignment_mode', 'mission_kind', 'source_type']:
        if field in request.data:
            val = request.data[field]
            # 空字符串转 None（Django DateTimeField 不接受空字符串）
            if field in ('start_at', 'end_at') and val == '':
                val = None
            if field == 'assignment_mode' and val not in ('flat', 'levels'):
                return Response({'code': 400, 'message': 'assignment_mode 无效', 'data': None, 'trace_id': make_trace_id()}, status=400)
            if field == 'mission_kind' and val not in ('regular', 'drill', 'wrongbook_personal'):
                return Response({'code': 400, 'message': 'mission_kind 无效', 'data': None, 'trace_id': make_trace_id()}, status=400)
            if field == 'source_type' and val not in ('question_bank', 'handout', 'wrongbook', 'ai_recommendation', 'teacher_matrix'):
                return Response({'code': 400, 'message': 'source_type 无效', 'data': None, 'trace_id': make_trace_id()}, status=400)
            setattr(mission, field, val)
    if 'target_student_ids' in request.data:
        mission.target_student_ids = request.data.get('target_student_ids') or []

    # Handle class_id separately (ForeignKey field)
    old_class_id = mission.class_obj_id
    if 'class_id' in request.data:
        class_id = request.data['class_id']
        if class_id:
            from apps.institutions.models import Class
            try:
                mission.class_obj = Class.objects.get(pk=class_id)
            except Class.DoesNotExist:
                pass
        else:
            mission.class_obj = None

    mission.save()

    if classes is not None:
        current = {str(item.class_obj_id): item for item in mission.class_assignments.all()}
        desired = {str(cls.id): cls for cls in classes}
        for class_id, assignment in current.items():
            if class_id not in desired and assignment.status != 'removed':
                assignment.status = 'removed'
                assignment.save(update_fields=['status', 'updated_at'])
        for class_id, cls in desired.items():
            assignment = current.get(class_id)
            if assignment:
                assignment.status = 'active'
                assignment.start_at = mission.start_at
                assignment.end_at = mission.end_at
                assignment.target_student_ids = list(mission.target_student_ids or [])
                assignment.save(update_fields=['status', 'start_at', 'end_at', 'target_student_ids', 'updated_at'])
            else:
                MissionClassAssignment.objects.create(
                    mission=mission, class_obj=cls, start_at=mission.start_at,
                    end_at=mission.end_at, target_student_ids=list(mission.target_student_ids or []),
                )

    # Keep progress rows for history, and add rows for newly assigned students.
    # This works for both a legacy class change and a multi-class update.
    if classes is not None or old_class_id != mission.class_obj_id:
        from apps.study.models import StudentMissionProgress
        for student_id in _mission_student_ids(mission):
            StudentMissionProgress.objects.get_or_create(
                mission=mission, student_user_id_id=student_id,
                defaults={'progress_status': 'not_started', 'progress_percent': 0},
            )
    return Response({'code': 0, 'message': '更新成功', 'data': None, 'trace_id': make_trace_id()})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_delete(request, mission_id):
    """M-04b: Delete mission (only draft missions can be deleted)."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    if mission.status != 'draft':
        return Response({
            'code': 400, 'message': '只能删除草稿状态的任务', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_400_BAD_REQUEST)

    # Delete related levels and question relations
    MissionLevel.objects.filter(mission=mission).delete()
    MissionQuestionRel.objects.filter(mission=mission).delete()
    mission.delete()

    return Response({'code': 0, 'message': '删除成功', 'data': None, 'trace_id': make_trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_levels(request, mission_id):
    """M-05: Add level to mission."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    serializer = CreateLevelSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    level = serializer.save(mission=mission)
    # Calls to this endpoint come from the legacy level-based workflow.
    mission.assignment_mode = 'levels'
    mission.save(update_fields=['assignment_mode', 'updated_at'])
    return Response({
        'code': 0, 'message': '关卡创建成功',
        'data': {'id': level.id}, 'trace_id': make_trace_id(),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_levels_batch(request, mission_id):
    """M-05b: Batch create levels with questions for a mission."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    serializer = BatchCreateLevelsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # 编辑模式：先删除旧关卡和题目关联，再创建新的
    old_levels = mission.levels.all()
    for old_lv in old_levels:
        MissionQuestionRel.objects.filter(level=old_lv).delete()
    old_levels.delete()

    level_ids = []
    for i, lv_data in enumerate(data['levels']):
        level = MissionLevel.objects.create(
            mission=mission,
            level_no=i + 1,
            level_name=lv_data.get('level_name') or lv_data.get('name') or f'第{i+1}关',
            level_type=lv_data.get('level_type') or lv_data.get('type') or 'practice',
            mode_policy=lv_data.get('mode_policy') or lv_data.get('mode') or 'block_a',
            pass_rule_json=lv_data.get('pass_rule_json') or lv_data.get('passRuleJson') or {},
            hint_strength=lv_data.get('hint_strength') or lv_data.get('hintStrength') or 'medium',
        )
        level_ids.append(level.id)

        # 添加题目到该关卡
        question_ids = lv_data.get('question_ids') or lv_data.get('questionIds') or []
        for j, qid in enumerate(question_ids):
            MissionQuestionRel.objects.create(
                mission=mission,
                level=level,
                question_id=qid,
                sort_no=j,
                is_required=True,
            )

    # This endpoint is the legacy level editor. Keep the mode explicit so a
    # flat assignment edited through an old client cannot be half-flat and
    # half-level based.
    mission.assignment_mode = 'levels'
    mission.save(update_fields=['assignment_mode', 'updated_at'])

    return Response({
        'code': 0, 'message': '关卡创建成功',
        'data': {'level_ids': level_ids}, 'trace_id': make_trace_id(),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_questions(request, mission_id):
    """M-06: Read questions or replace the flat assignment question list."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        from apps.study.serializers import QuestionListSerializer
        rels = ordered_mission_question_rels(mission)
        question_map = {
            str(question.id): question
            for question in ExamQuestion.objects.filter(id__in=[rel.question_id for rel in rels])
        }
        questions = [
            QuestionListSerializer(question_map[str(rel.question_id)]).data
            for rel in rels
            if str(rel.question_id) in question_map
        ]
        return Response({'code': 0, 'message': 'success', 'data': questions, 'trace_id': make_trace_id()})

    if 'question_ids' in request.data and 'level_id' not in request.data:
        serializer = FlatQuestionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question_ids = list(dict.fromkeys(serializer.validated_data['question_ids']))
        questions = list(ExamQuestion.objects.filter(pk__in=question_ids))
        if len(questions) != len(question_ids):
            return Response({'code': 400, 'message': '存在不存在的题目', 'data': None, 'trace_id': make_trace_id()}, status=400)
        from apps.study.question_views import _teacher_question_scope_error
        for question in questions:
            scope_error = _teacher_question_scope_error(request, question)
            if scope_error:
                return scope_error
        question_map = {str(question.id): question for question in questions}
        question_ids.sort(key=lambda question_id: question_no_sort_key(question_map[str(question_id)].question_no))
        level = ensure_flat_assignment_level(mission)
        MissionQuestionRel.objects.filter(mission=mission).delete()
        for sort_no, question_id in enumerate(question_ids, start=1):
            MissionQuestionRel.objects.create(
                mission=mission,
                level=level,
                question_id=question_id,
                sort_no=sort_no,
                is_required=True,
                source_type=request.data.get('source_type', 'manual_select'),
            )

        mission.assignment_mode = FLAT_ASSIGNMENT_MODE
        mission.save(update_fields=['assignment_mode', 'updated_at'])
        return Response({'code': 0, 'message': '题目保存成功', 'data': {'question_count': len(question_ids)}, 'trace_id': make_trace_id()})

    serializer = AddQuestionsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # Verify the level belongs to this mission
    try:
        level = MissionLevel.objects.get(pk=data['level_id'], mission=mission)
    except MissionLevel.DoesNotExist:
        return Response({
            'code': 400, 'message': '关卡不属于当前任务', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_400_BAD_REQUEST)

    question_rows = []
    for qid in data['question_ids']:
        try:
            question = ExamQuestion.objects.get(pk=qid)
        except ExamQuestion.DoesNotExist:
            return Response({'code': 400, 'message': f'题目不存在: {qid}', 'data': None, 'trace_id': make_trace_id()}, status=400)
        from apps.study.question_views import _teacher_question_scope_error
        scope_error = _teacher_question_scope_error(request, question)
        if scope_error:
            return scope_error
        question_rows.append((qid, question))
    question_rows.sort(key=lambda row: question_no_sort_key(row[1].question_no))
    for i, (qid, question) in enumerate(question_rows):
        MissionQuestionRel.objects.create(
            mission=mission,
            level=level,
            question_id=qid,
            sort_no=i,
            is_required=data['is_required'],
            source_type=request.data.get('source_type', 'manual_select'),
        )
    return Response({'code': 0, 'message': '题目添加成功', 'data': None, 'trace_id': make_trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_set_kind(request, mission_id, kind):
    """Set the teacher assignment kind; drill remains in the mission domain."""
    if kind not in ('regular', 'drill', 'wrongbook_personal'):
        return Response({'code': 400, 'message': '作业类型无效', 'data': None, 'trace_id': make_trace_id()}, status=400)
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)
    mission.mission_kind = kind
    source_type = request.data.get('source_type') or 'question_bank'
    if source_type not in ('question_bank', 'handout', 'wrongbook', 'ai_recommendation', 'teacher_matrix'):
        return Response({'code': 400, 'message': 'source_type 无效', 'data': None, 'trace_id': make_trace_id()}, status=400)
    mission.source_type = source_type
    mission.save(update_fields=['mission_kind', 'source_type', 'updated_at'])
    return Response({'code': 0, 'message': '作业类型已设置', 'data': {
        'mission_id': str(mission.id), 'mission_kind': mission.mission_kind,
        'source_type': mission.source_type,
    }, 'trace_id': make_trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_level_detail(request, mission_id, level_id):
    """M-09: Get level detail with questions (teacher side)."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        level = MissionLevel.objects.get(pk=level_id, mission=mission)
    except MissionLevel.DoesNotExist:
        return Response({
            'code': 404, 'message': '关卡不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    rels = [rel for rel in ordered_mission_question_rels(mission) if rel.level_id == level.id]
    questions = []
    for rel in rels:
        try:
            q = ExamQuestion.objects.get(pk=rel.question_id)
            images = []
            for image in q.images.all().order_by('sort_order'):
                # Formula snippets are already represented in stem/options text.  Only
                # send visual illustrations to the practice page; otherwise one question
                # can render several irrelevant formula crops and leave a large blank area.
                if not image.file_path or image.image_type == 'formula':
                    continue
                images.append({
                    'id': image.id,
                    # The client must receive a usable URL instead of a storage-relative path.
                    'url': _question_image_url(image.file_path),
                    'file_path': image.file_path,
                    'sort_order': image.sort_order,
                    'display_width': image.display_width,
                    'description': image.description or '',
                })
            questions.append({
                'id': q.id,
                'question_no': q.question_no,
                'question_type': q.question_type,
                'difficulty': float(q.difficulty) if q.difficulty else None,
                'stem': q.stem,
                'stem_html': q.stem_html,
                'answer': q.answer,
                'analysis': q.analysis,
                'images': images,
                'options': [{'label': o.option_label, 'content': o.content, 'sort_order': o.sort_order}
                           for o in q.options.all().order_by('sort_order')],
            })
        except ExamQuestion.DoesNotExist:
            continue

    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'level_id': level.id,
            'level_name': level.level_name,
            'level_type': level.level_type,
            'mode_policy': level.mode_policy,
            'questions': questions,
        }, 'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_publish(request, mission_id):
    """M-07: Publish mission and create progress records for class students."""
    close_stale_missions()
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    if mission.status == 'closed':
        return Response({'code': 400, 'message': '作业已自动关闭，不能发布', 'data': None, 'trace_id': make_trace_id()}, status=400)
    # Materialize the legacy class field into the relation before validating
    # publication. This is also safe for old missions created before P1.
    if mission.class_obj_id and not mission.class_assignments.filter(status='active').exists():
        MissionClassAssignment.objects.create(
            mission=mission, class_obj=mission.class_obj,
            start_at=mission.start_at, end_at=mission.end_at,
            target_student_ids=list(mission.target_student_ids or []),
        )
    assignments = _mission_assignments(mission)
    from apps.courses.models import Course
    course = Course.objects.filter(pk=mission.course_id).first() if mission.course_id else None
    classes, error = _validate_mission_classes(request.user, [a.class_obj_id for a in assignments], course)
    if error:
        return Response({'code': 403, 'message': error, 'data': None, 'trace_id': make_trace_id()}, status=403)
    # The simplified flow must have a completion date and at least one
    # question. Legacy level assignments keep the old publish contract.
    if mission.assignment_mode == FLAT_ASSIGNMENT_MODE:
        if not mission.end_at:
            return Response({'code': 400, 'message': '请设置完成日期', 'data': None, 'trace_id': make_trace_id()}, status=400)
        if not MissionQuestionRel.objects.filter(mission=mission).exists():
            return Response({'code': 400, 'message': '请至少选择一道题目', 'data': None, 'trace_id': make_trace_id()}, status=400)
        if not assignments and not (mission.target_student_ids or []):
            return Response({'code': 400, 'message': '请先选择班级或指定学生', 'data': None, 'trace_id': make_trace_id()}, status=400)

    # Generate before changing the status so a missing PDF dependency or an
    # invalid question set cannot publish a worksheet without its download.
    try:
        ensure_mission_pdf(mission)
    except ImportError:
        return Response({'code': 503, 'message': 'PDF dependency unavailable', 'data': None, 'trace_id': make_trace_id()}, status=503)
    except ValueError as exc:
        return Response({'code': 400, 'message': str(exc), 'data': None, 'trace_id': make_trace_id()}, status=400)

    # Publication and progress creation must be all-or-nothing. PDF generation
    # intentionally happens before this transaction because it is external I/O.
    from apps.study.models import StudentMissionProgress
    from apps.qrcode.services import ensure_mission_short_code, ensure_mission_short_codes
    with transaction.atomic():
        mission.status = 'published'
        mission.save(update_fields=['status', 'updated_at'])
        short_codes = ensure_mission_short_codes(mission)
        short_code = short_codes[0]
        created_count = 0
        for student_id in _mission_student_ids(mission):
            _, created = StudentMissionProgress.objects.get_or_create(
                mission=mission, student_user_id_id=student_id,
                defaults={'progress_status': 'not_started', 'progress_percent': 0},
            )
            created_count += int(created)
        assignment_result = [{
            'class_id': str(item.class_obj_id),
            'class_name': item.class_obj.class_name,
            'student_count': ClassStudent.objects.filter(
                class_obj_id=item.class_obj_id, status='active',
            ).count(),
            'status': item.status,
            'error': None,
        } for item in assignments]
        for row, code in zip(assignment_result, short_codes):
            row['short_code'] = code.short_code

    return Response({
        'code': 0, 'message': '发布成功',
        'data': {'students_notified': created_count, 'short_code': short_code.short_code,
                 'classes': assignment_result},
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_clone(request, mission_id):
    """M-08: Clone mission."""
    try:
        original = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    clone = LearningMission.objects.create(
        mission_name=f"{original.mission_name} (副本)",
        goal_text=original.goal_text,
        creator_teacher_id=request.user,
        start_at=original.start_at,
        end_at=original.end_at,
        default_mode_policy=original.default_mode_policy,
        assignment_mode=original.assignment_mode,
        mission_kind=original.mission_kind,
        source_type=original.source_type,
        class_obj=original.class_obj,
        target_student_ids=list(original.target_student_ids or []),
        course=original.course,
    )
    # Clone levels and questions
    for level in original.levels.all():
        new_level = MissionLevel.objects.create(
            mission=clone, level_no=level.level_no, level_name=level.level_name,
            level_type=level.level_type, pass_rule_json=level.pass_rule_json,
            mode_policy=level.mode_policy, hint_strength=level.hint_strength,
        )
        for rel in MissionQuestionRel.objects.filter(level=level):
            MissionQuestionRel.objects.create(
                mission=clone, level=new_level, question_id=rel.question_id,
                sort_no=rel.sort_no, is_required=rel.is_required,
                source_type=rel.source_type, target_student_ids=list(rel.target_student_ids or []),
            )
    for assignment in original.class_assignments.filter(status='active'):
        MissionClassAssignment.objects.create(
            mission=clone, class_obj=assignment.class_obj,
            start_at=assignment.start_at, end_at=assignment.end_at,
            target_student_ids=list(assignment.target_student_ids or []),
        )
    return Response({
        'code': 0, 'message': '复制成功',
        'data': {'id': clone.id}, 'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def mission_clone_with_class(request, mission_id):
    """M-09: Clone a mission and assign it to a different class with new deadlines."""
    try:
        original = LearningMission.objects.get(pk=mission_id)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    # Verify user is the teacher of the original mission OR a teacher of the target class
    class_id = request.data.get('class_id')
    if not class_id:
        return Response({
            'code': 400, 'message': 'class_id 不能为空', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verify user is a teacher of the target class
    from apps.institutions.models import ClassTeacher, Class
    try:
        target_class = Class.objects.get(pk=class_id)
    except Class.DoesNotExist:
        return Response({
            'code': 404, 'message': '班级不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not ClassTeacher.objects.filter(class_obj_id=class_id, teacher=request.user).exists():
        return Response({
            'code': 403, 'message': '您不是该班级的教师', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_403_FORBIDDEN)

    # Create clone with new class and deadlines
    clone = LearningMission.objects.create(
        mission_name=f"{original.mission_name} (副本)",
        goal_text=original.goal_text,
        creator_teacher_id=request.user,
        class_obj=target_class,
        start_at=request.data.get('start_at') or original.start_at,
        end_at=request.data.get('end_at'),  # Required for homework
        default_mode_policy=original.default_mode_policy,
        assignment_mode=original.assignment_mode,
        mission_kind=original.mission_kind,
        source_type=original.source_type,
        target_student_ids=list(original.target_student_ids or []),
    )
    MissionClassAssignment.objects.create(
        mission=clone, class_obj=target_class,
        start_at=clone.start_at, end_at=clone.end_at,
        target_student_ids=list(clone.target_student_ids or []),
    )

    # Clone levels and questions
    for level in original.levels.all():
        new_level = MissionLevel.objects.create(
            mission=clone, level_no=level.level_no, level_name=level.level_name,
            level_type=level.level_type, pass_rule_json=level.pass_rule_json,
            mode_policy=level.mode_policy, hint_strength=level.hint_strength,
        )
        for rel in MissionQuestionRel.objects.filter(level=level):
            MissionQuestionRel.objects.create(
                mission=clone, level=new_level, question_id=rel.question_id,
                sort_no=rel.sort_no, is_required=rel.is_required,
                source_type=rel.source_type, target_student_ids=list(rel.target_student_ids or []),
            )

    return Response({
        'code': 0, 'message': '复制成功',
        'data': {'id': clone.id, 'mission_no': clone.mission_no},
        'trace_id': make_trace_id(),
    })


# ============================================================
# Teacher B/C Mode Guidance
# ============================================================

# In-memory session store for teacher practice guidance
_teacher_guidance_sessions: dict = {}
guidance_component_factory = GuidanceComponent


def _question_image_url(file_path):
    """Return an API client-safe URL for a locally stored question image."""
    return media_url(file_path)


def _get_question_image_urls(question, max_images=3):
    """Get OSS URLs for question images."""
    images = list(QuestionImage.objects.filter(question=question).order_by('sort_order')[:max_images])
    urls = []
    for img in images:
        if img.file_path:
            urls.append(_question_image_url(img.file_path))
    return urls


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def start_teacher_guidance(request):
    """启动B/C模式引导。

    POST /api/v1/missions/guidance/start/
    Body: { "question_id": "<uuid>", "mode": "B" }  // mode: "B" or "C"
    """
    question_id = request.data.get('question_id')
    if not question_id:
        return Response({'code': 400, 'message': 'question_id is required'}, status=400)

    try:
        question_id = uuid.UUID(str(question_id))
    except (TypeError, ValueError, AttributeError):
        return Response({'code': 400, 'message': 'question_id must be a valid UUID'}, status=400)

    mode = request.data.get('mode', 'B')
    if mode not in ('B', 'C'):
        return Response({'code': 400, 'message': 'mode 必须为 B 或 C'}, status=400)

    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在'}, status=404)

    session_id = uuid.uuid4().hex[:16]

    if mode == 'B':
        # B模式：从 ai_answer_b 获取引导选项
        ai_b = q.ai_answer_b or {}
        if isinstance(ai_b, str):
            try:
                ai_b = json.loads(ai_b)
            except:
                ai_b = {}
        options = ai_b.get('options', [])
        hint = ai_b.get('hint', '请仔细阅读题目，思考关键条件。')
        # 如果 ai_answer_b 没有数据，使用默认引导
        if not options and not hint:
            hint = '这道题的关键条件是什么？请仔细阅读题干。'
            options = [
                '直接应用公式求解',
                '先分析已知条件',
                '画图辅助理解',
                '尝试代入具体数值',
            ]

        _teacher_guidance_sessions[session_id] = {
            'question_id': question_id,
            'mode': 'B',
            'turn': 0,
            'messages': [{'role': 'system', 'content': hint}],
            'options': options,
            'hint': hint,
        }

        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'session_id': session_id,
                'mode': 'B',
                'hint': hint,
                'options': options,
            }, 'trace_id': make_trace_id(),
        })
    else:
        # C模式：生成第一个引导问题
        ai_c = q.ai_answer_c or {}
        if isinstance(ai_c, str):
            try:
                ai_c = json.loads(ai_c)
            except:
                ai_c = {}

        first_question = ai_c.get('first_question') or ai_c.get('question') or '你觉得这道题的关键条件是什么？'

        _teacher_guidance_sessions[session_id] = {
            'question_id': question_id,
            'mode': 'C',
            'turn': 0,
            'messages': [{'role': 'system', 'content': first_question}],
            'first_question': first_question,
            'ai_c': ai_c,
        }

        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'session_id': session_id,
                'mode': 'C',
                'question': first_question,
            }, 'trace_id': make_trace_id(),
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def teacher_guidance_reply(request, session_id):
    """B/C模式引导回复。

    POST /api/v1/teacher/guidance/reply/{session_id}/
    Body: { "user_answer": "..." }
    """
    session = _teacher_guidance_sessions.get(session_id)
    if not session:
        return Response({'code': 404, 'message': '引导会话不存在'}, status=404)

    user_answer = request.data.get('user_answer', '')
    session['turn'] += 1
    session['messages'].append({'role': 'user', 'content': user_answer})

    question_id = session['question_id']
    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在'}, status=404)

    if session['mode'] == 'B':
        # B模式：返回下一步引导
        ai_b = q.ai_answer_b or {}
        if isinstance(ai_b, str):
            try:
                ai_b = json.loads(ai_b)
            except:
                ai_b = {}

        next_hint = ai_b.get('next_hint') or ai_b.get('hint') or '很好，继续思考下一个关键点。'
        session['messages'].append({'role': 'system', 'content': next_hint})

        # 检查是否完成（3轮后）
        is_completed = session['turn'] >= 3
        if is_completed:
            next_hint = '引导完成！你可以继续巩固或进入下一题。'

        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'next_hint': next_hint,
                'is_completed': is_completed,
                'mode': 'B',
                'turn': session['turn'],
            }, 'trace_id': make_trace_id(),
        })
    else:
        # C模式：调用Qwen评价用户回答，然后给出下一个引导问题
        ai_c = session.get('ai_c') or {}
        if not ai_c and q.ai_answer_c:
            ai_c = q.ai_answer_c
            if isinstance(ai_c, str):
                try:
                    ai_c = json.loads(ai_c)
                except:
                    ai_c = {}

        try:
            evaluation_result = (
                guidance_component_factory().evaluate_teacher_reply(
                    GuidanceContext(
                        question_text=q.stem or '',
                        reference_answer=q.answer or '',
                        student_answer=user_answer,
                    )
                )
            )
            evaluation = evaluation_result.get('evaluation')
            if not isinstance(evaluation, str) or not evaluation.strip():
                raise ValueError('AI guidance evaluation is missing')
        except AIConfigError:
            evaluation = '（AI评价功能暂不可用，请检查AI服务配置）'
        except AIResponseError:
            evaluation = '（AI评价调用失败：AIResponseError）'
        except Exception:
            evaluation = '（AI评价调用失败，请稍后重试）'

        # 获取下一个引导问题
        steps = ai_c.get('steps') or ai_c.get('dialogue') or []
        next_question = None
        if session['turn'] < len(steps):
            step = steps[session['turn']]
            if isinstance(step, dict):
                next_question = step.get('question') or step.get('prompt')
            elif isinstance(step, str):
                next_question = step

        if not next_question:
            if session['turn'] >= 3:
                next_question = '引导完成！你已经很好地理解了这道题。'
            else:
                next_question = '很好，请继续思考下一个问题。'

        session['messages'].append({'role': 'system', 'content': f'评价：{evaluation}\n\n{next_question}'})

        is_completed = session['turn'] >= 3

        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'evaluation': evaluation,
                'next_question': next_question,
                'is_completed': is_completed,
                'mode': 'C',
                'turn': session['turn'],
            }, 'trace_id': make_trace_id(),
        })
