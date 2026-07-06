import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt, StudentLevelProgress
from apps.wrongbook.models import WrongBookItem
from .feedback_engine import generate_feedback


def make_trace_id():
    return uuid.uuid4().hex[:16]


def _check_answer(question, answer_content: dict) -> bool:
    """Simple answer checking for MVP."""
    if question.question_type in ('single_choice', 'multiple_choice'):
        selected = set(answer_content.get('selected_options', []))
        # Get correct answer from AI analysis or answer field
        correct_str = getattr(question, 'answer', '') or ''
        if correct_str:
            correct = set(correct_str.replace(' ', '').upper())
        else:
            # Fallback: try to get from ai_answer_a
            ai_a = question.ai_answer_a or {}
            correct = set(str(ai_a.get('answer', '')).replace(' ', '').upper())
        return selected == correct
    # For subjective questions, mark as incorrect (needs AI review)
    return False


def _handle_submit_answer(request, question_id, answer_content, mission_id, level_id, source):
    """Core answer submission logic (shared by submit_answer and retry_answer)."""
    # Load question
    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    # Determine correctness
    is_correct = _check_answer(q, answer_content)

    # Count attempts
    attempt_no = AnswerAttempt.objects.filter(
        student_user_id=request.user, question_id=question_id
    ).count() + 1

    # Save attempt
    attempt = AnswerAttempt.objects.create(
        student_user_id=request.user,
        mission_id=mission_id, level_id=level_id,
        question_id=question_id, attempt_no=attempt_no,
        answer_content=answer_content, is_correct=is_correct,
        score=100.00 if is_correct else 0.00,
        submit_source=source,
    )

    # Update level progress
    if level_id:
        lp = StudentLevelProgress.objects.filter(
            level_id=level_id, student_user_id=request.user
        ).first()
        if lp:
            lp.attempt_count += 1
            if is_correct:
                lp.pass_score = max(lp.pass_score, 100.00)
            lp.save()

    # Wrong answer -> add to wrong book
    if not is_correct:
        WrongBookItem.objects.get_or_create(
            student_user_id=request.user, question_id=question_id,
            defaults={'status': 'not_reviewed'}
        )

    # Generate feedback
    feedback = generate_feedback(is_correct, q, attempt_no)

    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'is_correct': is_correct,
            'score': float(attempt.score),
            'feedback': feedback,
            'attempt_id': attempt.id,
            'suggest_guidance': not is_correct,
        }, 'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
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
@permission_classes([IsAuthenticated])
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
@permission_classes([IsAuthenticated])
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
