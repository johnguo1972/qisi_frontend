import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.models import AIGuidanceSession


def make_trace_id():
    return uuid.uuid4().hex[:16]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_guidance(request):
    """S-06: Start B/C guidance session."""
    question_id = request.data.get('question_id')
    mode_type = request.data.get('mode_type', 'B')

    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    # Create session
    session = AIGuidanceSession.objects.create(
        student_user_id=request.user,
        question_id=question_id,
        mode_type=mode_type,
        session_status='running',
        content_log_json={'steps': []},
    )

    # Generate initial guidance step
    if mode_type == 'B':
        # B mode: get options from ai_answer_b
        ai_b = q.ai_answer_b or {}
        options = ai_b.get('options', [])
        hint = ai_b.get('hint', '')
        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'session_id': session.id,
                'mode': 'B',
                'hint': hint,
                'options': options,
            }, 'trace_id': make_trace_id(),
        })
    else:
        # C mode: generate first question
        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'session_id': session.id,
                'mode': 'C',
                'question': '你觉得这道题的关键条件是什么？',
            }, 'trace_id': make_trace_id(),
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def guidance_reply(request, session_id):
    """S-07: Reply in guidance session."""
    try:
        session = AIGuidanceSession.objects.get(
            pk=session_id, student_user_id=request.user
        )
    except AIGuidanceSession.DoesNotExist:
        return Response({'code': 404, 'message': '引导会话不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    if session.session_status not in ('running',):
        return Response({'code': 4001, 'message': '引导已结束', 'data': None, 'trace_id': make_trace_id()}, status=400)

    user_reply = request.data.get('reply', '')

    # Log the step
    log = session.content_log_json
    if 'steps' not in log:
        log['steps'] = []
    log['steps'].append({'user': user_reply, 'turn': len(log['steps']) + 1})

    # Check if downgrade needed (2 invalid inputs)
    if session.mode_type == 'C' and len(user_reply.strip()) < 3:
        session.invalid_input_count += 1
        if session.invalid_input_count >= 2:
            session.mode_type = 'B'
            session.session_status = 'downgraded'
            session.save()
            return Response({
                'code': 0, 'message': '已降级到B模式',
                'data': {'mode': 'B', 'reason': '连续无效输入'},
                'trace_id': make_trace_id(),
            })

    # For MVP: after 3 turns, mark as completed
    if len(log['steps']) >= 3:
        session.session_status = 'completed'

    session.content_log_json = log
    session.save()

    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'session_status': session.session_status,
            'next_hint': '注意观察图形中的关键信息',
            'is_completed': session.session_status == 'completed',
        }, 'trace_id': make_trace_id(),
    })
