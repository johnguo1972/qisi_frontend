import json
import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudent
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.models import AIGuidanceSession
from .ai_helper import call_qwen_for_guidance


def make_trace_id():
    return uuid.uuid4().hex[:16]


def _as_dict(field):
    if not field:
        return {}
    if isinstance(field, dict):
        return field
    try:
        return json.loads(field)
    except Exception:
        return {}


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def start_guidance(request):
    """S-06: 启动引导，使用题目真实 ai_answer_b/c。"""
    question_id = request.data.get('question_id')
    mode_type = request.data.get('mode_type', 'B')
    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    ai_b = _as_dict(q.ai_answer_b)
    ai_c = _as_dict(q.ai_answer_c)

    session = AIGuidanceSession.objects.create(
        student_user_id=request.user, question_id=question_id,
        mode_type=mode_type, session_status='running',
        content_log_json={'step_index': 0, 'steps': []},
    )

    if mode_type == 'B':
        options = ai_b.get('options') or []
        hint = ai_b.get('hint') or '请仔细阅读题干，思考关键条件。'
        return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                         'data': {'session_id': session.id, 'mode': 'B', 'hint': hint, 'options': options}})

    first_q = ai_c.get('first_question') or ai_c.get('question') or '请从题干中找出你认为最关键的一个条件，并说明理由。'
    return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                     'data': {'session_id': session.id, 'mode': 'C', 'question': first_q}})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def guidance_reply(request, session_id):
    """S-07: 真实推进引导（B 走脚本，C 调 LLM 评价 + 步进 ai_answer_c.steps）。"""
    try:
        session = AIGuidanceSession.objects.get(pk=session_id, student_user_id=request.user)
    except AIGuidanceSession.DoesNotExist:
        return Response({'code': 404, 'message': '引导会话不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)
    if session.session_status != 'running':
        return Response({'code': 4001, 'message': '引导已结束', 'data': None, 'trace_id': make_trace_id()}, status=400)

    user_reply = (request.data.get('reply') or '').strip()
    try:
        q = ExamQuestion.objects.get(pk=session.question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    log = session.content_log_json or {'step_index': 0, 'steps': []}
    log.setdefault('steps', []).append({'user': user_reply})
    log['step_index'] = log.get('step_index', 0) + 1
    step_index = log['step_index']

    # C→B 降级（连续无效输入）
    if session.mode_type == 'C' and len(user_reply) < 3:
        session.invalid_input_count += 1
        if session.invalid_input_count >= 2:
            session.mode_type = 'B'
            session.session_status = 'downgraded'
            session.content_log_json = log
            session.save()
            return Response({'code': 0, 'message': '已降级到B模式', 'trace_id': make_trace_id(),
                             'data': {'mode': 'B', 'reason': '连续无效输入', 'is_completed': False}})

    ai_b = _as_dict(q.ai_answer_b)
    ai_c = _as_dict(q.ai_answer_c)

    if session.mode_type == 'B':
        next_hint = ai_b.get('next_hint') or ai_b.get('hint') or '很好，继续思考下一个关键点。'
        is_completed = step_index >= 3
        if is_completed:
            next_hint = '引导完成！可以返回做题页继续。'
        session.content_log_json = log
        session.session_status = 'completed' if is_completed else 'running'
        session.save()
        return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                         'data': {'next_hint': next_hint, 'is_completed': is_completed, 'mode': 'B'}})

    # C 模式：真实 LLM 评价 + 步进 ai_answer_c.steps
    evaluation = call_qwen_for_guidance(
        '你是一位耐心的老师，对学生回答给出 1-2 句简明评价与鼓励。',
        f'题目：{q.stem}\n参考答案：{q.answer or "见解析"}\n学生回答：{user_reply}\n请评价。',
    )
    steps = ai_c.get('steps') or ai_c.get('dialogue') or []
    next_question = None
    if step_index < len(steps):
        st = steps[step_index]
        next_question = st.get('question') or st.get('prompt') if isinstance(st, dict) else st
    if not next_question:
        next_question = '引导完成！你已经很好地理解了这道题。' if step_index >= 3 else '很好，请继续思考下一步。'
    is_completed = step_index >= 3

    session.content_log_json = log
    session.session_status = 'completed' if is_completed else 'running'
    session.save()

    return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                     'data': {'evaluation': evaluation, 'next_hint': next_question,
                              'next_question': next_question, 'is_completed': is_completed, 'mode': 'C'}})
