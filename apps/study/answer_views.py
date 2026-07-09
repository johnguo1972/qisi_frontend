import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudent
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt, StudentLevelProgress
from apps.wrongbook.models import WrongBookItem
from .feedback_engine import generate_feedback


def make_trace_id():
    return uuid.uuid4().hex[:16]


SUBJECTIVE_TYPES = ('fill_blank', 'short_answer', 'essay', 'true_false', 'computation', 'proof')


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
    # 主观题无法自动判分 → None
    return None


def _handle_submit_answer(request, question_id, answer_content, mission_id, level_id, source):
    """Core answer submission logic (shared by submit_answer and retry_answer)."""
    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    result = _check_answer(q, answer_content)
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
        feedback = generate_feedback(is_correct, q, attempt_no)

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
@permission_classes([IsAuthenticated, IsStudent])
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


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
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
@permission_classes([IsAuthenticated, IsStudent])
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
