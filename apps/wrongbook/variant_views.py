"""变式题练习：提交答案、判分、更新错题计数与掌握度。"""
import uuid
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudent
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt
from .models import WrongBookItem, MasteryRecord


def make_trace_id():
    return uuid.uuid4().hex[:16]


OBJECTIVE_TYPES = ('single_choice', 'multiple_choice')


def _grade(question, answer_content):
    """客观题 True/False；主观题 None（待批阅）。"""
    if question.question_type in OBJECTIVE_TYPES:
        selected = set(answer_content.get('selected_options', []))
        correct_str = getattr(question, 'answer', '') or ''
        if correct_str:
            correct = set(correct_str.replace(' ', '').upper())
        else:
            ai_a = question.ai_answer_a or {}
            correct = set(str(ai_a.get('answer', '')).replace(' ', '').upper())
        return selected == correct
    return None


def _update_mastery(student, question_id: int, is_correct: bool):
    """按题目维度更新掌握度：答对 +50（满 100 mastered），答错 -20。"""
    mr, _ = MasteryRecord.objects.get_or_create(
        student_user_id=student, mastery_type='question', target_code=str(question_id),
        defaults={'mastery_status': 'not_mastered', 'mastery_score': 0},
    )
    if is_correct:
        mr.mastery_score = min(100, float(mr.mastery_score) + 50)
        if mr.mastery_score >= 100:
            mr.mastery_status = 'mastered'
    else:
        mr.mastery_score = max(0, float(mr.mastery_score) - 20)
        mr.mastery_status = 'reviewing'
    mr.save()


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def variant_submit(request, item_id):
    """POST /api/v1/student/wrong-book/<item_id>/variant-submit
    Body: { question_id, answer_content }
    """
    trace_id = make_trace_id()
    question_id = request.data.get('question_id')
    answer_content = request.data.get('answer_content', {})

    try:
        item = WrongBookItem.objects.get(pk=item_id, student_user_id=request.user)
    except WrongBookItem.DoesNotExist:
        return Response({'code': 404, 'message': '错题不存在', 'data': None, 'trace_id': trace_id}, status=404)

    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': trace_id}, status=404)

    result = _grade(q, answer_content)
    is_pending = result is None
    is_correct = False if is_pending else result

    with transaction.atomic():
        attempt = AnswerAttempt.objects.create(
            student_user_id=request.user,
            mission_id=None, level_id=None,
            question_id=question_id,
            attempt_no=AnswerAttempt.objects.filter(
                student_user_id=request.user, question_id=question_id).count() + 1,
            answer_content=answer_content,
            is_correct=is_correct,
            is_subjective_pending=is_pending,
            score=100.00 if is_correct else 0.00,
            submit_source='variant',
        )
        # 错题状态推进：not_reviewed → reviewing(首次练) → mastered(累计练对≥3)
        if item.status == 'not_reviewed':
            item.status = 'reviewing'
        if is_correct and not is_pending:
            item.variant_done_count = (item.variant_done_count or 0) + 1
            if item.variant_done_count >= 3:
                item.status = 'mastered'
        item.save(update_fields=['variant_done_count', 'status'])
        _update_mastery(request.user, question_id, is_correct and not is_pending)

    if is_pending:
        feedback = '主观题已提交，等待老师批阅'
    elif is_correct:
        feedback = '做对了！该错题掌握度已提升。'
    else:
        feedback = '再想想，注意与原题的相同考点。'

    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'is_correct': is_correct,
            'is_pending': is_pending,
            'score': float(attempt.score),
            'feedback': feedback,
            'variant_done_count': item.variant_done_count,
            'item_status': item.status,
        }, 'trace_id': trace_id,
    })
