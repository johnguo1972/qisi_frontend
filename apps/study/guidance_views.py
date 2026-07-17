import json
import uuid
from datetime import timedelta
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudent
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.models import AIGuidanceSession
from .ai_helper import call_qwen_for_guidance, call_qwen_for_guidance_with_question


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


def _is_invalid_reply(reply: str) -> bool:
    """判断学生回答是否有效（简单规则，无需 LLM）。"""
    if not reply or len(reply) < 3:
        return True
    INVALID_PATTERNS = ['不知道', '不会', '不懂', '没想法', '跳过', 'pass', '不会做', '不想做']
    if any(p in reply for p in INVALID_PATTERNS):
        return True
    return False


def _build_question_info(q) -> dict:
    """从 ExamQuestion 对象提取题干和选项，用于引导页展示原题。"""
    # 预加载 option 关联避免 N+1，但这里只有单个对象，直接查询
    from apps.parser.models import QuestionOption as _QuestionOption
    return {
        'stem': q.stem or '',
        'stem_html': q.stem_html or '',
        'question_type': q.question_type,
        'options': [
            {'label': o.option_label, 'content': o.content}
            for o in _QuestionOption.objects.filter(question=q).order_by('sort_order')
        ],
        'images': [
            {'id': img.id, 'file_path': img.file_path}
            for img in q.images.all()
        ],
    }


def _extract_b_mode_step(ai_b: dict, step_index: int) -> dict:
    """从 ai_answer_b 中提取指定步骤的引导数据。

    返回: {
        'hint': str,           # 当前步骤的引导问题
        'options': list,       # ["A. 内容", "B. 内容", "C. 内容", "D. 内容"]
        'correct_option': str, # 正确答案标签（兜底时为空字符串，表示无正确性判断）
        'analysis': str,       # 该步骤解析（兜底时为空）
    }
    如果 ai_b 为空或无数据，返回通用兜底数据。
    """
    questions = (ai_b or {}).get('questions') or []
    if questions and step_index < len(questions):
        q = questions[step_index]
        opts = q.get('options') or {}
        return {
            'hint': q.get('question', '请思考下一步'),
            'options': [f"{k}. {v}" for k, v in opts.items() if k in ('A', 'B', 'C', 'D')],
            'correct_option': q.get('correct_option', ''),
            'analysis': q.get('analysis', ''),
        }
    # 兜底：通用引导选项（无 correct_option，表示不判断正确性）
    FALLBACK_B_STEPS = [
        {'hint': '请仔细阅读题干，分析题目的已知条件和未知条件', 'options': [
            'A. 分析已知条件，找出关键信息',
            'B. 思考适用的公式或定理',
            'C. 尝试代入具体数值进行验证',
            'D. 回顾相关知识点，建立解题思路',
        ]},
        {'hint': '根据第一步的分析，尝试列出解题所需的公式或步骤', 'options': [
            'A. 列出所有已知公式',
            'B. 确定解题顺序',
            'C. 代入数值进行计算',
            'D. 验证结果的合理性',
        ]},
        {'hint': '最后检查你的答案，确认是否完整且符合题意', 'options': [
            'A. 答案已完整，可以提交',
            'B. 需要补充中间步骤',
            'C. 需要重新检查计算',
            'D. 需要换个思路',
        ]},
    ]
    if step_index < len(FALLBACK_B_STEPS):
        return {**FALLBACK_B_STEPS[step_index], 'correct_option': '', 'analysis': ''}
    return {'hint': '引导完成', 'options': [], 'correct_option': '', 'analysis': ''}


def _extract_c_mode_step(ai_c: dict, step_index: int) -> dict:
    """从 ai_answer_c 中提取指定步骤的开放引导问题。

    返回: {
        'question': str,  # 引导问题
        'reference_answer': str,  # 参考答案
        'key_points': list,  # 关键点
    }
    """
    questions = (ai_c or {}).get('questions') or []
    if questions and step_index < len(questions):
        q = questions[step_index]
        return {
            'question': q.get('question', '请继续思考'),
            'reference_answer': q.get('reference_answer', ''),
            'key_points': q.get('key_points', []),
        }
    # 兜底
    return {
        'question': '请继续思考这道题的解题思路',
        'reference_answer': '',
        'key_points': [],
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def start_guidance(request):
    """S-06: 启动引导。当 mode_type 为空时根据题型自动推荐。"""
    question_id = request.data.get('question_id')
    mode_type = request.data.get('mode_type', '')
    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    # 清理 24 小时前的运行中 session（避免堆积）
    AIGuidanceSession.objects.filter(
        student_user_id=request.user,
        session_status='running',
        created_at__lt=timezone.now() - timedelta(hours=24)
    ).update(session_status='expired')

    # 前端未指定模式时，根据题型自动推荐
    if not mode_type:
        if q.question_type in ('single_choice', 'multiple_choice'):
            mode_type = 'B'
        else:
            mode_type = 'C'

    ai_b = _as_dict(q.ai_answer_b)
    ai_c = _as_dict(q.ai_answer_c)

    # 创建 session
    session = AIGuidanceSession.objects.create(
        student_user_id=request.user, question_id=question_id,
        mode_type=mode_type, session_status='running',
        content_log_json={'step_index': 0, 'steps': [], 'answers': []},
    )

    # B 模式处理
    if mode_type == 'B':
        questions = (ai_b or {}).get('questions') or []
        total_steps = len(questions) or 3  # 动态计算：AI 数据有就用 AI 的，否则固定 3 步兜底
        step_data = _extract_b_mode_step(ai_b, 0)
        is_fallback = not questions
        return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                         'data': {
                             'session_id': session.id, 'mode': 'B',
                             'step_index': 0, 'total_steps': total_steps,
                             'hint': step_data['hint'], 'options': step_data['options'],
                             'is_fallback': is_fallback,
                             'question_info': _build_question_info(q),
                         }})

    # C 模式处理
    questions = (ai_c or {}).get('questions') or []
    total_steps = len(questions) or 3

    if questions:
        # 优先使用 ai_answer_c 的预置数据
        step_data = _extract_c_mode_step(ai_c, 0)
        return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                         'data': {
                             'session_id': session.id, 'mode': 'C',
                             'step_index': 0, 'total_steps': total_steps,
                             'hint': step_data['question'],
                             'question_info': _build_question_info(q),
                         }})

    # ai_answer_c 为空：实时调用 LLM 生成
    try:
        generated = call_qwen_for_guidance_with_question(q.stem, q.answer)
        if generated and generated.get('steps'):
            llm_steps = generated['steps']
            total_steps = len(llm_steps)
            # 将 steps 转成 questions 格式，存入 session 供后续 guidance_reply 使用
            converted_questions = []
            for step in llm_steps:
                converted_questions.append({
                    'question': step.get('question', '请继续思考'),
                    'reference_answer': step.get('hint', ''),
                    'key_points': step.get('key_points', []),
                })
            log = session.content_log_json or {'step_index': 0, 'steps': [], 'answers': []}
            log['ai_c_generated'] = {'questions': converted_questions}
            session.content_log_json = log
            session.save(update_fields=['content_log_json'])

            first_q = llm_steps[0]['question']
            return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                             'data': {
                                 'session_id': session.id, 'mode': 'C',
                                 'step_index': 0, 'total_steps': total_steps,
                                 'hint': first_q,
                                 'question_info': _build_question_info(q),
                             }})
    except Exception:
        pass

    # LLM 也失败：降级到 B 模式
    session.mode_type = 'B'
    session.session_status = 'downgraded'
    session.save()
    questions_b = (ai_b or {}).get('questions') or []
    total_steps_b = len(questions_b) or 3
    step_data = _extract_b_mode_step(ai_b, 0)
    return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                     'data': {
                         'session_id': session.id, 'mode': 'B',
                         'step_index': 0, 'total_steps': total_steps_b,
                         'hint': step_data['hint'], 'options': step_data['options'],
                         'downgraded': True,
                         'downgrade_reason': '非固定选项引导数据不可用，已降级到固定选项引导模式',
                         'question_info': _build_question_info(q),
                     }})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def guidance_reply(request, session_id):
    """S-07: 推进引导（B 模式分步判断 + C 模式 LLM 评价 + 步进）。"""
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

    ai_b = _as_dict(q.ai_answer_b)
    ai_c = _as_dict(q.ai_answer_c)

    log = session.content_log_json or {'step_index': 0, 'steps': [], 'answers': []}
    step_index = log.get('step_index', 0)
    evaluation = None  # 初始化，供 C 模式使用

    # C→B 降级（连续无效输入）
    if session.mode_type == 'C' and _is_invalid_reply(user_reply):
        session.invalid_input_count += 1
        if session.invalid_input_count >= 2:
            session.mode_type = 'B'
            session.session_status = 'downgraded'
            session.content_log_json = log
            session.save()
            # 降级后返回 B 模式的第一步
            questions_b = (ai_b or {}).get('questions') or []
            total_steps = len(questions_b) or 3
            step_data = _extract_b_mode_step(ai_b, 0)
            return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                             'data': {
                                 'mode': 'B', 'step_index': 0, 'total_steps': total_steps,
                                 'next_hint': step_data['hint'], 'options': step_data['options'],
                                 'downgraded': True, 'downgrade_reason': '连续无效输入，已降级到固定选项引导',
                                 'is_completed': False,
                             }})

    # 获取当前步骤的数据
    if session.mode_type == 'B':
        questions = (ai_b or {}).get('questions') or []
        total_steps = len(questions) or 3
        step_data = _extract_b_mode_step(ai_b, step_index)
        # 兜底时 correct_option 为空，跳过正确性判断
        is_correct = None
        if step_data['correct_option']:
            is_correct = user_reply == step_data['correct_option']
        log.setdefault('answers', []).append({
            'step': step_index, 'user_answer': user_reply,
            'correct_answer': step_data['correct_option'], 'is_correct': is_correct,
        })

    if session.mode_type == 'C':
        # 优先从 ai_answer_c 读取，若为空则尝试从 session 的 content_log_json 读取 LLM 实时生成的数据
        c_questions = (ai_c or {}).get('questions') or []
        if not c_questions:
            c_questions = (log.get('ai_c_generated') or {}).get('questions') or []
        total_steps = len(c_questions) or 3
        # 调用 LLM 进行评价（失败时返回兜底文案）
        try:
            evaluation = call_qwen_for_guidance(
                '你是一位耐心的老师，对学生回答给出 1-2 句简明评价与鼓励。',
                f'题目：{q.stem}\n参考答案：{q.answer or "见解析"}\n学生回答：{user_reply}\n请评价。',
            )
        except Exception:
            evaluation = '（AI 评价暂不可用）'
        log.setdefault('answers', []).append({
            'step': step_index, 'user_answer': user_reply,
        })

    # 推进到下一步
    next_step = step_index + 1
    log['step_index'] = next_step
    is_completed = next_step >= total_steps

    # 未完成 → 返回下一步数据
    if not is_completed:
        if session.mode_type == 'B':
            next_data = _extract_b_mode_step(ai_b, next_step)
            session.content_log_json = log
            session.save()
            return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                             'data': {
                                 'mode': 'B', 'step_index': next_step, 'total_steps': total_steps,
                                 'is_correct': is_correct,
                                 'correct_answer': step_data['correct_option'],
                                 'analysis': step_data['analysis'],
                                 'next_hint': next_data['hint'],
                                 'options': next_data['options'],
                                 'is_completed': False,
                             }})
        else:
            next_data = _extract_c_mode_step({'questions': c_questions}, next_step)
            session.content_log_json = log
            session.save()
            return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                             'data': {
                                 'mode': 'C', 'step_index': next_step, 'total_steps': total_steps,
                                 'evaluation': evaluation,
                                 'next_hint': next_data['question'],
                                 'is_completed': False,
                             }})

    # 已完成 → 返回总结
    session.session_status = 'completed'
    session.content_log_json = log
    session.save()

    # 获取 summary/final_answer：优先从 ai_answer_b/c 读取，若为空则尝试从 LLM 生成数据读取
    if session.mode_type == 'B':
        summary = (ai_b or {}).get('summary', '')
        final_answer = (ai_b or {}).get('final_answer', '')
    else:
        summary = (ai_c or {}).get('summary', '') or (log.get('ai_c_generated') or {}).get('summary', '')
        final_answer = (ai_c or {}).get('final_answer', '') or (log.get('ai_c_generated') or {}).get('final_answer', '')

    return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                     'data': {
                         'mode': session.mode_type,
                         'step_index': next_step, 'total_steps': total_steps,
                         'is_completed': True,
                         'summary': summary,
                         'final_answer': final_answer,
                         'is_correct': is_correct if session.mode_type == 'B' else None,
                         'correct_answer': step_data.get('correct_option', '') if session.mode_type == 'B' else None,
                         'analysis': step_data.get('analysis', '') if session.mode_type == 'B' else None,
                         'evaluation': evaluation if session.mode_type == 'C' else None,
                     }})