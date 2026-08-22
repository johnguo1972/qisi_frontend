"""变式题练习：提交答案、判分、更新错题计数与掌握度。"""
import re
import uuid
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudentOnly
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt
from .models import WrongBookItem, MasteryRecord
from .services import find_variant_questions


def make_trace_id():
    return uuid.uuid4().hex[:16]


OBJECTIVE_TYPES = ('single_choice', 'multiple_choice')


def _option_letters(value):
    """Extract option labels from plain or LaTeX answers such as ``D`` or ``$\\mathrm{D}$``."""
    text = str(value or '').replace('\\\\', '\\')
    formatted = re.findall(r'\\(?:mathrm|text)\s*\{\s*([A-D])\s*\}', text, re.IGNORECASE)
    if formatted:
        return {letter.upper() for letter in formatted}
    return {letter.upper() for letter in re.findall(r'(?<![A-Za-z])([A-D])(?![A-Za-z])', text)}


def _effective_question_type(question):
    question_type = str(question.question_type or '').strip().lower()
    if question_type not in {'', 'unknown'}:
        return question_type

    stem = str(question.stem or '').replace('\\\\', '\\')
    if re.search(r'选填|填空|\\underline|_{2,}', stem, re.IGNORECASE):
        return 'fill_blank'
    if re.search(r'\u5224\u65ad|\u6b63\u786e|\u9519\u8bef|\u5bf9\u9519', stem, re.IGNORECASE):
        return 'true_false'
    if re.search(r'\\mathrm\s*\{[A-D]\}|(?:^|[\n])\s*[A-D][.．、]', stem, re.IGNORECASE):
        return 'single_choice'
    return question_type


def _grade(question, answer_content):
    """客观题 True/False；主观题 None（待批阅）。"""
    if not isinstance(answer_content, dict):
        return False

    question_type = _effective_question_type(question)
    if question_type in OBJECTIVE_TYPES:
        selected_values = answer_content.get('selected_options', [])
        if isinstance(selected_values, str):
            selected_values = [selected_values]
        selected = _option_letters(''.join(str(value) for value in (selected_values or [])))
        correct_str = getattr(question, 'answer', '') or ''
        if correct_str:
            correct = _option_letters(correct_str)
        else:
            ai_a = question.ai_answer_a or {}
            correct = _option_letters(ai_a.get('answer', ''))
        return selected == correct
    if question_type == 'true_false':
        selected_values = answer_content.get('selected_options', [])
        selected = selected_values[0] if isinstance(selected_values, list) and selected_values else answer_content.get('selected', '')
        selected = str(selected or '').strip().lower()
        correct = str(getattr(question, 'answer', '') or '').strip().lower()
        aliases = {'正确': 'true', '对': 'true', 't': 'true', 'true': 'true', '是': 'true',
                   '错误': 'false', '错': 'false', 'f': 'false', 'false': 'false', '否': 'false'}
        return aliases.get(selected, selected) == aliases.get(correct, correct)
    if question_type == 'fill_blank':
        student_text = str(answer_content.get('text', '') or '')
        correct_text = str(getattr(question, 'answer', '') or '')
        split_pattern = r'[,，;；、\n]+'
        student_parts = [part.strip().lower() for part in re.split(split_pattern, student_text) if part.strip()]
        correct_parts = [part.strip().lower() for part in re.split(split_pattern, correct_text) if part.strip()]
        return bool(correct_parts) and student_parts == correct_parts
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
@permission_classes([IsAuthenticated, IsStudentOnly])
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

    if not isinstance(answer_content, dict):
        return Response({
            'code': 400,
            'message': 'answer_content 必须是对象',
            'data': None,
            'trace_id': trace_id,
        }, status=400)

    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except (ExamQuestion.DoesNotExist, TypeError, ValueError):
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': trace_id}, status=404)

    # The path parameter identifies the source wrong-book item, while
    # question_id identifies the selected variant.  Keep the two namespaces
    # separate and only accept variants returned for this source item.
    allowed_question_ids = {
        str(variant['id'])
        for variant in find_variant_questions(item.question_id, limit=3)
    }
    if str(q.id) not in allowed_question_ids:
        return Response({
            'code': 404,
            'message': '题目不是该错题的同类题',
            'data': None,
            'trace_id': trace_id,
        }, status=404)

    result = _grade(q, answer_content)
    is_pending = result is None
    is_correct = False if is_pending else result

    with transaction.atomic():
        attempt = AnswerAttempt.objects.create(
            student_user_id=request.user,
            mission_id=None, level_id=None,
            question_id=q.id,
            attempt_no=AnswerAttempt.objects.filter(
                student_user_id=request.user, question_id=q.id).count() + 1,
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
        _update_mastery(request.user, q.id, is_correct and not is_pending)

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
            'correct_answer': q.answer or (q.ai_answer_a or {}).get('answer', ''),
            'analysis': q.analysis or q.solution or '',
        }, 'trace_id': trace_id,
    })
