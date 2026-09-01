import uuid
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudentOnly, IsStudentOrParentContext
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt, StudentLevelProgress, StudentMissionProgress
from apps.missions.models import LearningMission, MissionQuestionRel
from apps.missions.services import mission_visible_to_student, ordered_mission_question_rels
from apps.missions.snapshots import apply_snapshot_to_question, mission_question_relation
from apps.wrongbook.models import WrongBookItem
from .feedback_engine import generate_feedback


def make_trace_id():
    return uuid.uuid4().hex[:16]


import re

SUBJECTIVE_TYPES = ('short_answer', 'essay', 'computation', 'proof')


def _normalize_answer(text: str) -> str:
    """标准化答案文本：去除空格、转小写、全角转半角。"""
    text = text.strip()
    text = text.replace(' ', '').replace('　', '')
    text = text.lower()
    # 全角转半角
    result = []
    for c in text:
        code = ord(c)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            result.append(' ')
        else:
            result.append(c)
    return ''.join(result)


def _check_answer(question, answer_content: dict):
    """客观题返回 True/False；主观题返回 None（待批阅）。"""
    if question.question_type in ('single_choice', 'multiple_choice'):
        selected = set(answer_content.get('selected_options', []))
        correct_str = getattr(question, 'answer', '') or ''
        if correct_str:
            correct = set(correct_str.replace(' ', '').upper())
        else:
            # Fallback: try to get from ai_answer_a
            ai_a = question.ai_answer_a or {}
            correct = set(str(ai_a.get('answer', '')).replace(' ', '').upper())
        return selected == correct
    if question.question_type == 'true_false':
        selected = answer_content.get('selected', '') or ''
        correct_str = getattr(question, 'answer', '') or ''
        return selected.strip().upper() == correct_str.strip().upper()
    if question.question_type == 'fill_blank':
        student_text = answer_content.get('text', '') or ''
        correct_str = getattr(question, 'answer', '') or ''
        # 按中文分号或逗号分隔多个空位的答案
        student_answers = re.split(r'[；;，,、|]+', _normalize_answer(student_text))
        correct_answers = re.split(r'[；;，,、|]+', _normalize_answer(correct_str))
        # 过滤空值
        student_answers = [a for a in student_answers if a]
        correct_answers = [a for a in correct_answers if a]
        if not correct_answers:
            return False
        # 逐一比对
        if len(student_answers) != len(correct_answers):
            return False
        return all(s == c for s, c in zip(student_answers, correct_answers))
    # 主观题无法自动判分 → None
    return None


def _mission_question_error(request, mission_id, question_id, level_id=None):
    """Ensure a submission belongs to the student's published assignment."""
    if not mission_id:
        return None
    try:
        mission = LearningMission.objects.get(pk=mission_id, status='published')
    except LearningMission.DoesNotExist:
        return Response({'code': 403, 'message': '作业不存在或未发布', 'data': None, 'trace_id': make_trace_id()}, status=403)
    from apps.institutions.models import ClassStudent
    student = getattr(request, '_effective_student', request.user)
    class_ids = ClassStudent.objects.filter(
        student=student, status='active',
    ).values_list('class_obj_id', flat=True)
    if not mission_visible_to_student(mission, student.id, class_ids):
        return Response({'code': 403, 'message': '无权提交该作业', 'data': None, 'trace_id': make_trace_id()}, status=403)
    if not StudentMissionProgress.objects.filter(mission=mission, student_user_id=student).exists():
        return Response({'code': 403, 'message': '无权提交该作业', 'data': None, 'trace_id': make_trace_id()}, status=403)
    rel = MissionQuestionRel.objects.filter(mission=mission, question_id=question_id)
    if level_id:
        rel = rel.filter(level_id=level_id)
    if not rel.exists():
        return Response({'code': 403, 'message': '题目不属于该作业', 'data': None, 'trace_id': make_trace_id()}, status=403)
    if StudentMissionProgress.objects.filter(mission=mission, student_user_id=request.user, progress_status__in=('submitted', 'graded', 'completed', 'passed')).exists():
        return Response({'code': 409, 'message': '作业已全部提交，不能继续修改', 'data': None, 'trace_id': make_trace_id()}, status=409)
    return None


def _update_mission_progress(mission, student, final=False):
    if not mission:
        return
    required = list(dict.fromkeys(MissionQuestionRel.objects.filter(
        mission=mission, is_required=True,
    ).values_list('question_id', flat=True)))
    latest = {}
    for attempt in AnswerAttempt.objects.filter(mission=mission, student_user_id=student, question_id__in=required).exclude(submit_source='draft').order_by('question_id', '-submitted_at'):
        latest.setdefault(str(attempt.question_id), attempt)
    answered = sum(1 for attempt in latest.values() if attempt.submit_source != 'draft')
    percent = round(answered / len(required) * 100, 2) if required else 0
    progress, _ = StudentMissionProgress.objects.get_or_create(
        mission=mission, student_user_id=student,
        defaults={'progress_status': 'not_started', 'progress_percent': 0},
    )
    if final and answered >= len(required):
        progress.progress_status = 'graded' if not any(a.is_subjective_pending for a in latest.values()) else 'submitted'
    elif answered:
        progress.progress_status = 'in_progress'
    progress.progress_percent = percent
    progress.save(update_fields=['progress_status', 'progress_percent', 'last_action_at'])


def _handle_submit_answer(request, question_id, answer_content, mission_id, level_id, source):
    """Core answer submission logic (shared by submit_answer and retry_answer)."""
    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    mission_error = _mission_question_error(request, mission_id, q.id, level_id)
    if mission_error:
        return mission_error
    grading_question = apply_snapshot_to_question(
        q, mission_question_relation(mission_id, q.id, level_id) if mission_id else None,
    )
    idempotency_key = str(request.data.get('idempotency_key') or request.headers.get('Idempotency-Key') or '').strip()
    if idempotency_key:
        existing = AnswerAttempt.objects.filter(
            student_user_id=request.user, mission_id=mission_id,
            question_id=question_id, idempotency_key=idempotency_key,
        ).first()
        if existing:
            return Response({'code': 0, 'message': 'success', 'data': {
                'is_correct': existing.is_correct, 'is_pending': existing.is_subjective_pending,
                'score': float(existing.score), 'attempt_id': str(existing.id), 'idempotent_replay': True,
            }, 'trace_id': make_trace_id()})

    result = _check_answer(grading_question, answer_content)
    is_pending = result is None                       # 主观题
    is_correct = False if is_pending else result

    attempt_no = AnswerAttempt.objects.filter(
        student_user_id=request.user, question_id=question_id
    ).count() + 1

    attempt = AnswerAttempt.objects.create(
        student_user_id=request.user,
        mission_id=mission_id, level_id=level_id,
        question_id=question_id, attempt_no=attempt_no,
        answer_content=answer_content, is_correct=is_correct,
        is_subjective_pending=is_pending,
        score=100.00 if is_correct else 0.00,
        submit_source=source,
        idempotency_key=idempotency_key,
    )

    if level_id:
        lp = StudentLevelProgress.objects.filter(
            level_id=level_id, student_user_id=request.user
        ).first()
        if lp:
            lp.attempt_count += 1
            if is_correct:
                lp.pass_score = max(lp.pass_score, 100.00)
            lp.save()

    # 仅“客观题答错”才进错题本；主观题待批阅不进
    if (not is_correct) and (not is_pending):
        WrongBookItem.objects.get_or_create(
            student_user_id=request.user, question_id=question_id,
            defaults={'status': 'not_reviewed'}
        )

    if is_pending:
        feedback = '主观题已提交，等待老师批阅'
    else:
        feedback = generate_feedback(is_correct, grading_question, attempt_no)

    _update_mission_progress(
        LearningMission.objects.filter(pk=mission_id).first() if mission_id else None,
        request.user,
    )
    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'is_correct': is_correct,
            'is_pending': is_pending,
            'score': float(attempt.score),
            'feedback': feedback,
            'attempt_id': attempt.id,
            'suggest_guidance': (not is_correct) and (not is_pending),
        }, 'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudentOnly])
def start_attempt(request):
    """Create a draft attempt so image answers have an owner before upload."""
    question_id = request.data.get('question_id')
    try:
        question = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    mission_error = _mission_question_error(
        request, request.data.get('mission_id'), question.id, request.data.get('level_id')
    )
    if mission_error:
        return mission_error

    attempt_no = AnswerAttempt.objects.filter(
        student_user_id=request.user, question_id=question.id,
    ).count() + 1
    attempt = AnswerAttempt.objects.create(
        student_user_id=request.user,
        mission_id=request.data.get('mission_id'),
        level_id=request.data.get('level_id'),
        question_id=question.id,
        attempt_no=attempt_no,
        answer_content={},
        is_correct=False,
        is_subjective_pending=True,
        submit_source='draft',
    )
    return Response({'code': 0, 'message': 'success', 'data': {'attempt_id': attempt.id}, 'trace_id': make_trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudentOnly])
def submit_attempt(request, attempt_id):
    """Finalize a draft attempt after optional image uploads."""
    try:
        attempt = AnswerAttempt.objects.get(pk=attempt_id, student_user_id=request.user)
    except AnswerAttempt.DoesNotExist:
        return Response({'code': 404, 'message': '作答记录不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)
    if attempt.submit_source != 'draft':
        return Response({'code': 409, 'message': '作答记录已经提交', 'data': None, 'trace_id': make_trace_id()}, status=409)
    try:
        question = ExamQuestion.objects.get(pk=attempt.question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    answer_content = request.data.get('answer_content', {})
    grading_question = apply_snapshot_to_question(
        question,
        mission_question_relation(attempt.mission_id, attempt.question_id, attempt.level_id)
        if attempt.mission_id else None,
    )
    result = _check_answer(grading_question, answer_content)
    is_pending = result is None
    is_correct = False if is_pending else result
    attempt.answer_content = answer_content
    attempt.is_correct = is_correct
    attempt.is_subjective_pending = is_pending
    attempt.score = 100.00 if is_correct else 0.00
    attempt.submit_source = request.data.get('source', 'manual')
    attempt.save(update_fields=['answer_content', 'is_correct', 'is_subjective_pending', 'score', 'submit_source'])

    if attempt.level_id:
        lp = StudentLevelProgress.objects.filter(level_id=attempt.level_id, student_user_id=request.user).first()
        if lp:
            lp.attempt_count += 1
            if is_correct:
                lp.pass_score = max(lp.pass_score, 100.00)
            lp.save(update_fields=['attempt_count', 'pass_score'])
    if (not is_correct) and (not is_pending):
        WrongBookItem.objects.get_or_create(
            student_user_id=request.user, question_id=attempt.question_id,
            defaults={'status': 'not_reviewed'},
        )
    feedback = '主观题已提交，等待老师批阅' if is_pending else generate_feedback(is_correct, grading_question, attempt.attempt_no)
    _update_mission_progress(
        LearningMission.objects.filter(pk=attempt.mission_id).first() if attempt.mission_id else None,
        request.user,
    )
    return Response({'code': 0, 'message': 'success', 'data': {
        'is_correct': is_correct, 'is_pending': is_pending, 'score': float(attempt.score),
        'feedback': feedback, 'attempt_id': attempt.id,
        'suggest_guidance': (not is_correct) and (not is_pending),
    }, 'trace_id': make_trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudentOnly])
def submit_answer(request):
    """S-04: Submit answer."""
    return _handle_submit_answer(
        request,
        question_id=request.data.get('question_id'),
        answer_content=request.data.get('answer_content', {}),
        mission_id=request.data.get('mission_id'),
        level_id=request.data.get('level_id'),
        source=request.data.get('source', 'manual'),
    )


def _mission_required_relations(mission, student):
    """Return required relations visible to this student in display order."""
    # Keep the result order identical to the order used by the student level
    # API and the exported worksheet.  UUID ordering or the original question
    # bank number must not make the answer result sequence diverge.
    relations = [
        relation for relation in ordered_mission_question_rels(mission)
        if relation.is_required
    ]
    return [
        relation for relation in relations
        if not relation.target_student_ids
        or str(student.id) in {str(value) for value in relation.target_student_ids}
    ]


def _answer_content_has_value(answer_content):
    """Decide whether a batch answer contains an actual student response."""
    if not isinstance(answer_content, dict):
        return False
    selected_options = answer_content.get('selected_options')
    if isinstance(selected_options, (list, tuple)) and any(
        str(value).strip() for value in selected_options
    ):
        return True
    for key in ('selected', 'text', 'answer', 'content'):
        value = answer_content.get(key)
        if value is not None and str(value).strip():
            return True
    images = answer_content.get('images')
    return isinstance(images, (list, tuple)) and any(
        str(value).strip() for value in images
    )


def _mission_result_items(mission, student, relations=None):
    """Build answer/analysis data that is only returned after final submission."""
    relations = relations or _mission_required_relations(mission, student)
    question_ids = list(dict.fromkeys(str(relation.question_id) for relation in relations))
    attempts = AnswerAttempt.objects.filter(
        mission=mission, student_user_id=student, question_id__in=question_ids,
    ).exclude(submit_source='draft').order_by('question_id', '-submitted_at')
    latest = {}
    for attempt in attempts:
        latest.setdefault(str(attempt.question_id), attempt)

    items = []
    seen = set()
    display_no = 0
    for relation in relations:
        question_id = str(relation.question_id)
        if question_id in seen:
            continue
        seen.add(question_id)
        display_no += 1
        question = ExamQuestion.objects.filter(pk=relation.question_id).first()
        if not question:
            continue
        grading_question = apply_snapshot_to_question(question, relation)
        attempt = latest.get(question_id)
        items.append({
            'question_id': question_id,
            'level_id': str(relation.level_id),
            # ``question_no`` is the number shown in this mission, not the
            # original question-bank number.  A generated wrong-question
            # mission may contain source questions numbered 3 and 4, but the
            # student must see them as questions 1 and 2 in that mission.
            'question_no': display_no,
            'source_question_no': question.question_no,
            'is_correct': attempt.is_correct if attempt else None,
            'is_pending': attempt.is_subjective_pending if attempt else False,
            'answer_content': attempt.answer_content if attempt else {},
            'answer': getattr(grading_question, 'answer', '') or '',
            'analysis': getattr(grading_question, 'analysis', '') or '',
            'solution': getattr(grading_question, 'solution', '') or '',
        })
    return items


def _submit_mission_batch(mission, student, progress, raw_answers):
    """Persist and grade answers supplied by the final whole-mission submit."""
    if not isinstance(raw_answers, list):
        return Response({
            'code': 400, 'message': 'answers 必须是数组',
            'data': None, 'trace_id': make_trace_id(),
        }, status=400)

    relations = _mission_required_relations(mission, student)
    relation_by_question = {}
    for relation in relations:
        relation_by_question.setdefault(str(relation.question_id), relation)

    answer_by_question = {}
    duplicate_ids = []
    for item in raw_answers:
        if not isinstance(item, dict) or not item.get('question_id'):
            return Response({
                'code': 400, 'message': '答案缺少 question_id',
                'data': None, 'trace_id': make_trace_id(),
            }, status=400)
        question_id = str(item['question_id'])
        if question_id in answer_by_question:
            duplicate_ids.append(question_id)
        answer_by_question[question_id] = item

    invalid_ids = sorted(set(answer_by_question) - set(relation_by_question))
    if invalid_ids or duplicate_ids:
        return Response({
            'code': 400, 'message': '答案中包含无效或重复题目',
            'data': {
                'invalid_question_ids': invalid_ids,
                'duplicate_question_ids': sorted(set(duplicate_ids)),
            }, 'trace_id': make_trace_id(),
        }, status=400)

    question_ids = list(relation_by_question)
    existing_attempts = AnswerAttempt.objects.filter(
        mission=mission, student_user_id=student, question_id__in=question_ids,
    ).order_by('question_id', '-submitted_at')
    latest = {}
    for attempt in existing_attempts:
        if attempt.submit_source != 'draft':
            latest.setdefault(str(attempt.question_id), attempt)

    saved_count = 0
    for question_id, item in answer_by_question.items():
        answer_content = item.get('answer_content', {})
        if not isinstance(answer_content, dict) or not _answer_content_has_value(answer_content):
            continue

        relation = relation_by_question[question_id]
        question = ExamQuestion.objects.filter(pk=relation.question_id).first()
        if not question:
            continue
        grading_question = apply_snapshot_to_question(question, relation)
        result = _check_answer(grading_question, answer_content)
        is_pending = result is None
        is_correct = False if is_pending else result
        idempotency_key = str(item.get('idempotency_key') or '').strip()[:100]
        attempt = None

        attempt_id = item.get('attempt_id')
        if attempt_id:
            try:
                attempt = AnswerAttempt.objects.filter(
                    pk=attempt_id, mission=mission, student_user_id=student,
                    question_id=relation.question_id,
                ).first()
            except (TypeError, ValueError):
                attempt = None
        if attempt is None and idempotency_key:
            attempt = AnswerAttempt.objects.filter(
                mission=mission, student_user_id=student,
                question_id=relation.question_id, idempotency_key=idempotency_key,
            ).order_by('-submitted_at').first()
        if attempt is None:
            attempt = AnswerAttempt.objects.filter(
                mission=mission, student_user_id=student,
                question_id=relation.question_id, submit_source='draft',
            ).order_by('-submitted_at').first()

        if attempt is None:
            attempt = AnswerAttempt.objects.create(
                student_user_id=student,
                mission=mission,
                level_id=relation.level_id,
                question_id=relation.question_id,
                attempt_no=AnswerAttempt.objects.filter(
                    student_user_id=student, question_id=relation.question_id,
                ).count() + 1,
                answer_content=answer_content,
                is_correct=is_correct,
                is_subjective_pending=is_pending,
                score=100.00 if is_correct else 0.00,
                submit_source='manual',
                idempotency_key=idempotency_key,
                image_count=len(answer_content.get('images') or []),
            )
        else:
            attempt.answer_content = answer_content
            attempt.is_correct = is_correct
            attempt.is_subjective_pending = is_pending
            attempt.score = 100.00 if is_correct else 0.00
            attempt.submit_source = 'manual'
            if idempotency_key:
                attempt.idempotency_key = idempotency_key
            attempt.image_count = len(answer_content.get('images') or [])
            attempt.save(update_fields=[
                'answer_content', 'is_correct', 'is_subjective_pending', 'score',
                'submit_source', 'idempotency_key', 'image_count',
            ])

        latest[question_id] = attempt
        saved_count += 1
        if (not is_correct) and (not is_pending):
            WrongBookItem.objects.get_or_create(
                student_user_id=student, question_id=relation.question_id,
                defaults={'status': 'not_reviewed'},
            )

    missing = [
        question_id for question_id in question_ids
        if question_id not in latest or latest[question_id].submit_source == 'draft'
    ]
    if missing:
        _update_mission_progress(mission, student, final=False)
        return Response({
            'code': 400, 'message': '还有题目未作答',
            'data': {
                'missing_question_ids': missing,
                'saved_count': saved_count,
            }, 'trace_id': make_trace_id(),
        }, status=400)

    _update_mission_progress(mission, student, final=True)
    progress.refresh_from_db()
    return Response({
        'code': 0, 'message': '作业提交成功',
        'data': {
            'status': progress.progress_status,
            'progress_percent': float(progress.progress_percent),
            'results': _mission_result_items(mission, student, relations),
        }, 'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudentOnly])
@transaction.atomic
def submit_mission(request, mission_id):
    """Submit the whole mission, leaving it unchanged when required answers are missing."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, status='published')
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': '作业不存在或未发布', 'data': None, 'trace_id': make_trace_id()}, status=404)
    from apps.institutions.models import ClassStudent
    student = getattr(request, '_effective_student', request.user)
    class_ids = ClassStudent.objects.filter(
        student=student, status='active',
    ).values_list('class_obj_id', flat=True)
    if not mission_visible_to_student(mission, student.id, class_ids):
        return Response({'code': 403, 'message': '无权提交该作业', 'data': None, 'trace_id': make_trace_id()}, status=403)
    progress = StudentMissionProgress.objects.select_for_update().filter(
        mission=mission, student_user_id=student,
    ).first()
    # 重复提交直接返回当前状态，避免重复推进任务状态。completed 不在
    # 终态列表中，兼容旧逻辑在逐题完成后提前写入 completed 的数据。
    if progress and progress.progress_status in ('submitted', 'graded', 'passed'):
        return Response({'code': 0, 'message': '作业已提交', 'data': {
            'status': progress.progress_status,
            'progress_percent': float(progress.progress_percent),
            'idempotent_replay': True,
        }, 'trace_id': make_trace_id()})
    if progress and 'answers' in request.data:
        return _submit_mission_batch(mission, student, progress, request.data.get('answers'))
    if not progress:
        return Response({'code': 403, 'message': '无权提交该作业', 'data': None, 'trace_id': make_trace_id()}, status=403)
    required = list(dict.fromkeys(MissionQuestionRel.objects.filter(
        mission=mission, is_required=True,
    ).values_list('question_id', flat=True)))
    latest = {}
    for attempt in AnswerAttempt.objects.filter(mission=mission, student_user_id=student, question_id__in=required).exclude(submit_source='draft').order_by('question_id', '-submitted_at'):
        latest.setdefault(str(attempt.question_id), attempt)
    missing = [str(question_id) for question_id in required if str(question_id) not in latest or latest[str(question_id)].submit_source == 'draft']
    if missing:
        return Response({'code': 400, 'message': '还有题目未提交', 'data': {'missing_question_ids': missing}, 'trace_id': make_trace_id()}, status=400)
    _update_mission_progress(mission, student, final=True)
    progress = StudentMissionProgress.objects.get(mission=mission, student_user_id=student)
    return Response({'code': 0, 'message': '作业提交成功', 'data': {
        'status': progress.progress_status, 'progress_percent': float(progress.progress_percent),
    }, 'trace_id': make_trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOnly])
def mission_results(request, mission_id):
    """Return the complete answer result after whole-mission submission."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, status='published')
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': '作业不存在或未发布', 'data': None, 'trace_id': make_trace_id()}, status=404)

    from apps.institutions.models import ClassStudent
    student = getattr(request, '_effective_student', request.user)
    class_ids = ClassStudent.objects.filter(
        student=student, status='active',
    ).values_list('class_obj_id', flat=True)
    if not mission_visible_to_student(mission, student.id, class_ids):
        return Response({'code': 403, 'message': '无权查看该作业结果', 'data': None, 'trace_id': make_trace_id()}, status=403)
    progress = StudentMissionProgress.objects.filter(
        mission=mission, student_user_id=student,
    ).first()
    if not progress:
        return Response({'code': 403, 'message': '无权查看该作业结果', 'data': None, 'trace_id': make_trace_id()}, status=403)
    if progress.progress_status not in ('submitted', 'graded', 'passed'):
        return Response({'code': 409, 'message': '作业尚未整份提交', 'data': None, 'trace_id': make_trace_id()}, status=409)
    return Response({'code': 0, 'message': 'success', 'data': {
        'status': progress.progress_status,
        'progress_percent': float(progress.progress_percent),
        'results': _mission_result_items(mission, student),
    }, 'trace_id': make_trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOrParentContext])
def related_questions(request, question_id):
    """Return assigned candidate questions after the source was submitted."""
    student = getattr(request, '_effective_student', request.user)
    source = ExamQuestion.objects.filter(pk=question_id).first()
    if not source:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)
    if not AnswerAttempt.objects.filter(
        student_user_id=student, question_id=question_id,
    ).exclude(submit_source='draft').exists():
        return Response({'code': 403, 'message': '请先提交原题后再查看关联题', 'data': None, 'trace_id': make_trace_id()}, status=403)

    from apps.institutions.models import ClassStudent
    class_ids = set(ClassStudent.objects.filter(
        student=student, status='active',
    ).values_list('class_obj_id', flat=True))
    visible_missions = [
        mission for mission in LearningMission.objects.filter(status='published')
        if mission_visible_to_student(mission, student.id, class_ids)
    ]
    visible_relations = MissionQuestionRel.objects.filter(
        mission_id__in=[mission.id for mission in visible_missions],
    ).select_related('mission')
    visible_ids = {
        str(rel.question_id)
        for rel in visible_relations
        if not rel.target_student_ids or str(student.id) in {
            str(value) for value in rel.target_student_ids
        }
    }
    visible_ids.discard(str(question_id))
    query = ExamQuestion.objects.filter(id__in=visible_ids).filter(subject=source.subject).order_by('difficulty', 'id')[:20]
    items = [{
        'id': str(item.id), 'question_no': item.question_no,
        'question_type': item.question_type, 'stem': item.stem or '',
        'stem_html': item.stem_html or '',
        'options': [{'label': option.option_label, 'content': option.content} for option in item.options.order_by('sort_order', 'id')],
        'knowledge_points': item.knowledge_points or [], 'can_practice': True,
    } for item in query]
    return Response({'code': 0, 'message': 'success', 'data': items, 'trace_id': make_trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudentOnly])
def retry_answer(request, attempt_id):
    """S-05: Retry wrong answer."""
    try:
        original = AnswerAttempt.objects.get(pk=attempt_id, student_user_id=request.user)
    except AnswerAttempt.DoesNotExist:
        return Response({'code': 404, 'message': '作答记录不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    # Forward to shared logic with source='retry' and original question/level/mission
    return _handle_submit_answer(
        request,
        question_id=original.question_id,
        answer_content=request.data.get('answer_content', {}),
        mission_id=original.mission_id,
        level_id=original.level_id,
        source='retry',
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOrParentContext])
def get_mode_a(request, question_id):
    """S-08: Get structured answer A."""
    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    # Check if student has attempted this question
    has_attempted = AnswerAttempt.objects.filter(
        student_user_id=request.user, question_id=question_id
    ).exists()

    if not has_attempted:
        return Response({
            'code': 4003, 'message': '请先尝试作答后再查看答案',
            'data': None, 'trace_id': make_trace_id(),
        }, status=403)

    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'ai_answer_a': q.ai_answer_a,
            'question_no': q.question_no,
        },
        'trace_id': make_trace_id(),
    })
