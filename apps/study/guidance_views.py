import json
import hashlib
import logging
import re
import time
import uuid
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudentOnly, IsStudentOrParentContext
from rest_framework.response import Response
from apps.parser.models import ExamQuestion
from apps.study.models import AIGuidanceSession
from apps.common.ai.components import (
    GuidanceComponent,
    GuidanceContext,
    QuestionInput,
)
from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.exceptions import AIRequestError
from apps.common.media import media_url


guidance_component_factory = GuidanceComponent
logger = logging.getLogger(__name__)


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


def _normalize_b_option(value: str) -> str:
    """将 B 模式回答统一为选项标签，兼容标签或完整选项文本。"""
    if not isinstance(value, str):
        return ''
    normalized = value.strip()
    match = re.match(r'^([A-Da-d])(?:\s*[.．、:：)]|\s+|$)', normalized)
    return match.group(1).upper() if match else normalized.upper()


def _fixed_option_text(options, option_label):
    """Return the visible text for one fixed-guidance option."""
    prefix = f'{option_label}.'
    for option in options or []:
        text = str(option or '').strip()
        if text.upper().startswith(prefix.upper()):
            return text[len(prefix):].strip()
        if text[:1].upper() == option_label.upper() and len(text) > 1:
            return text[1:].lstrip('.．、:：) ').strip()
    return ''


def _build_fixed_guidance_selection_result(
    step_data, selected_option, is_correct=None, next_data=None,
    next_question=None, next_hint=None,
):
    """Build a B response using only the current step and AI/step data."""
    next_data = next_data or {}
    next_question = str(next_question or '').strip() or None
    next_hint = str(next_hint or '').strip() or next_question
    branch = {
        'step_index': step_data.get('step_index', 0),
        'selected_option': selected_option,
        'selected_option_text': _fixed_option_text(
            step_data.get('options'), selected_option
        ),
        'step_question': step_data.get('question') or step_data.get('hint') or '',
        'feedback': '',
        'selection_feedback': '',
        'next_question': next_question,
        'next_hint': next_hint,
        'next_options': list(next_data.get('options') or []) if next_question else [],
        'action_is_correct': is_correct,
    }
    return {'fixed_guidance': branch}


def _build_question_info_uncached(q) -> dict:
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
            {
                'id': img.id,
                'file_path': img.file_path,
                'url': media_url(img.file_path),
                'image_type': img.image_type,
                'display_width': img.display_width,
                'description': img.description or '',
            }
            for img in q.images.all().order_by('sort_order')
            if img.file_path and img.image_type != 'formula'
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
            'correct_option': _normalize_b_option(q.get('correct_option', '')),
            'analysis': q.get('analysis', ''),
            'is_fallback': False,
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
        return {
            **FALLBACK_B_STEPS[step_index],
            'correct_option': '',
            'analysis': '',
            'is_fallback': True,
        }
    return {
        'hint': '引导完成', 'options': [], 'correct_option': '',
        'analysis': '', 'is_fallback': True,
    }


def _extract_c_mode_step(ai_c: dict, step_index: int) -> dict:
    """从 ai_answer_c 中提取指定步骤的开放引导问题。

    返回: {
        'question': str,  # 引导问题
        'reference_answer': str,  # 参考答案
        'key_points': list,  # 关键点
    }
    """
    questions = (ai_c or {}).get('questions') or []
    if not questions:
        # Keep the preparation-pending response readable even when the
        # historical fallback literal is encountered.
        return {
            'question': '请继续思考这道题的解题思路',
            'reference_answer': '',
            'key_points': [],
        }
    if questions and step_index < len(questions):
        q = questions[step_index]
        return {
            'question': q.get('question', '请继续思考'),
            'reference_answer': q.get('reference_answer', ''),
            'key_points': q.get('key_points', []),
        }
    # 兜底
    cache_key = _question_context_cache_key(q)
    if cache_key:
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            logger.debug('Guidance question context cache read failed', exc_info=True)

    result = {
        'question': '请继续思考这道题的解题思路',
        'reference_answer': '',
        'key_points': [],
    }
    if cache_key:
        try:
            cache.set(cache_key, result, timeout=300)
        except Exception:
            logger.debug('Guidance question context cache write failed', exc_info=True)
    return result


def _question_context_cache_key(q) -> str | None:
    question_id = getattr(q, 'pk', None) or getattr(q, 'id', None)
    if not question_id:
        return None
    version = getattr(q, 'updated_at', None)
    version_text = version.isoformat() if version else 'current'
    digest = hashlib.sha256(version_text.encode('utf-8')).hexdigest()[:12]
    return f'guidance:question-context:{question_id}:{digest}'


def _guidance_ai_enabled(user) -> bool:
    if not bool(getattr(settings, 'GUIDANCE_REALTIME_AI_ENABLED', True)):
        return False
    allowlist = getattr(settings, 'GUIDANCE_GRAY_MOBILES', ()) or ()
    if isinstance(allowlist, str):
        allowlist = tuple(value.strip() for value in allowlist.split(',') if value.strip())
    return not allowlist or str(getattr(user, 'mobile', '') or '').strip() in allowlist


def _guidance_model_manager():
    manager = AIGuidanceSession.objects
    selector = getattr(manager, 'select_for_update', None)
    return selector() if callable(selector) else manager


@contextmanager
def _guidance_atomic():
    """Use row transactions in production while keeping isolated view tests lightweight."""
    if isinstance(AIGuidanceSession, type) and issubclass(AIGuidanceSession, models.Model):
        with transaction.atomic():
            yield
    else:
        yield


def _guidance_reply_key(session_id, step_index: int, mode: str, reply: str, reply_id: str = '') -> str:
    if reply_id:
        return f'id:{reply_id}'
    raw = f'{session_id}:{step_index}:{mode}:{reply}'
    return 'sha256:' + hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _find_reply_log(log: dict, reply_key: str, reply_id: str = '') -> dict | None:
    for entry in reversed((log or {}).get('answers') or []):
        if entry.get('reply_key') != reply_key and (
            not reply_id or entry.get('reply_id') != reply_id
        ):
            continue
        return entry
    return None


def _pending_reply_is_live(entry: dict) -> bool:
    started_text = entry.get('started_at')
    if not started_text:
        return True
    try:
        started_at = timezone.datetime.fromisoformat(started_text)
    except (TypeError, ValueError):
        return True
    if timezone.is_naive(started_at):
        started_at = timezone.make_aware(started_at, timezone.get_current_timezone())
    return timezone.now() - started_at < timedelta(seconds=60)


def _replace_reply_log(log: dict, reply_key: str, entry: dict) -> None:
    answers = log.setdefault('answers', [])
    for index in range(len(answers) - 1, -1, -1):
        if answers[index].get('reply_key') == reply_key:
            answers[index] = entry
            return
    answers.append(entry)


def _response_payload(data: dict, trace_id: str) -> dict:
    return {'code': 0, 'message': 'success', 'trace_id': trace_id, 'data': data}


def _enqueue_guidance_preparation(question) -> None:
    """Schedule missing C content; never block the student start request."""
    if bool(getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)):
        logger.info('Guidance C preparation skipped in eager Celery mode', extra={
            'question_id': str(getattr(question, 'pk', '')),
        })
        return
    try:
        from apps.study.tasks import prepare_guidance_content

        prepare_guidance_content.delay(str(question.pk))
    except Exception:
        # The student can continue with the safe C fallback and/or B downgrade.
        logger.exception('Unable to enqueue guidance C preparation')


def _build_question_info(q) -> dict:
    """Return the question display/context payload with a short-lived cache."""
    cache_key = _question_context_cache_key(q)
    if cache_key:
        try:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            logger.debug('Guidance question context cache read failed', exc_info=True)
    result = _build_question_info_uncached(q)
    if cache_key:
        try:
            cache.set(cache_key, result, timeout=300)
        except Exception:
            logger.debug('Guidance question context cache write failed', exc_info=True)
    return result


def _build_guidance_context(
    q, mode, step_data, user_reply, log, trace_id, program_is_correct=None
):
    """组装一次评价所需的完整题目、步骤、视觉和历史上下文。"""
    question_info = _build_question_info(q) or {}
    raw_visual_facts = getattr(q, 'ai_vision_extract', None)
    if isinstance(raw_visual_facts, (list, tuple)):
        visual_facts = list(raw_visual_facts)
    elif raw_visual_facts:
        visual_facts = [raw_visual_facts]
    else:
        visual_facts = []
    for image in question_info.get('images') or []:
        if isinstance(image, dict) and image.get('description'):
            visual_facts.append(image['description'])

    analysis = ''
    for field_name in ('analysis', 'solution', 'raw_explanation', 'comment'):
        value = getattr(q, field_name, '') or ''
        if value:
            analysis = value
            break

    knowledge_points = getattr(q, 'knowledge_points', None)
    if not knowledge_points:
        knowledge_points = getattr(q, 'ai_knowledge_enrichment', None)
    if isinstance(knowledge_points, (list, tuple)):
        knowledge_points = list(knowledge_points)
    elif knowledge_points:
        knowledge_points = [knowledge_points]
    else:
        knowledge_points = []

    if mode == 'B':
        current_reference_answer = '\n'.join(
            value for value in (
                f"正确选项：{step_data.get('correct_option', '')}"
                if step_data.get('correct_option') else '',
                f"步骤解析：{step_data.get('analysis', '')}"
                if step_data.get('analysis') else '',
            )
            if value
        )
    else:
        current_reference_answer = step_data.get('reference_answer', '') or ''

    key_points = step_data.get('key_points') or []
    if not isinstance(key_points, (list, tuple)):
        key_points = [key_points]
    history = (log or {}).get('answers') or []
    original_question_options = tuple(question_info.get('options') or [])
    image_urls = _fixed_guidance_image_sources(question_info) if mode == 'B' else ()
    fixed_guidance_step = {
        'question': step_data.get('question') or step_data.get('hint') or '',
        'options': list(step_data.get('options') or []),
    }
    if mode == 'C':
        fixed_guidance_step['reference_answer'] = (
            step_data.get('reference_answer', '') or ''
        )
        fixed_guidance_step['key_points'] = list(key_points)
    return GuidanceContext(
        question_text=getattr(q, 'stem', '') or '',
        reference_answer=getattr(q, 'answer', '') or '',
        student_answer=user_reply,
        trace_id=trace_id,
        mode=mode,
        current_question=(
            step_data.get('question') or step_data.get('hint') or ''
        ),
        current_reference_answer=current_reference_answer,
        key_points=tuple(key_points),
        question_options=tuple(
            step_data.get('options') or question_info.get('options') or []
        ),
        question_analysis=analysis,
        knowledge_points=tuple(knowledge_points),
        visual_facts=tuple(visual_facts),
        image_urls=image_urls,
        history=tuple(history[-5:]),
        program_is_correct=program_is_correct,
        original_question_text=getattr(q, 'stem', '') or '',
        original_question_options=original_question_options,
        fixed_guidance_step=fixed_guidance_step,
        student_selected_guidance_step=user_reply,
        guidance_step_is_correct=program_is_correct,
    )


def _fixed_guidance_image_sources(question_info: dict) -> tuple[str, ...]:
    """Return provider-safe sources for the fixed guidance vision request.

    The student API intentionally returns relative browser URLs.  Fixed
    guidance must not send those URLs to the remote provider because the
    provider cannot resolve the student's local host.  Prefer the stored
    media file and let ``prepare_image_sources`` validate/encode it later.
    """
    media_root = Path(settings.MEDIA_ROOT).resolve()
    sources = []
    for image in question_info.get('images') or []:
        if not isinstance(image, dict):
            continue
        file_path = str(image.get('file_path') or '').strip()
        if file_path:
            candidate = Path(file_path)
            if not candidate.is_absolute():
                candidate = media_root / candidate
            try:
                candidate = candidate.resolve()
                candidate.relative_to(media_root)
            except (OSError, ValueError):
                continue
            sources.append(str(candidate))
            continue
        source = str(image.get('url') or '').strip()
        if source.startswith(('https://', 'http://', 'data:')):
            sources.append(source)
    return tuple(sources)


def _normalize_guidance_result(result):
    """Normalize structured component output while keeping old injected clients safe."""
    defaults = {
        'result': 'unclear',
        'error_type': 'unclear',
        'evaluation': str(result or 'AI 评价暂时不可用，请稍后重试'),
        'correction_direction': '请结合当前引导问题补充你的解题依据。',
        'next_question': None,
        'next_hint': None,
        'confidence': 0.0,
    }
    if isinstance(result, dict):
        defaults.update({
            key: result[key]
            for key in defaults
            if key in result
        })
    return defaults


def _normalize_fixed_guidance_result(result):
    """Normalize the dedicated B-mode AI response without C-mode fields."""
    defaults = {
        'feedback': '请结合当前固定引导动作继续思考。',
        'known_information': '请先从题干和图片中提取与本步骤相关的信息。',
        'guidance': '请根据当前固定引导动作完成下一步分析，不直接给出原题答案。',
        'next_question': None,
        'next_hint': None,
        'confidence': 0.0,
    }
    if isinstance(result, dict):
        defaults.update({key: result[key] for key in defaults if key in result})
    return defaults


def _build_guidance_format_fallback(mode, step_data, is_correct=None):
    """Recover from a malformed model payload without making another AI call."""
    if mode == 'B':
        if is_correct is True:
            evaluation = '已收到你的回答，选项判断与当前参考答案一致。请继续说明作出判断的依据。'
            result = 'correct'
            error_type = 'none'
        elif is_correct is False:
            evaluation = '已收到你的回答，但该选项与当前参考答案不一致。请对照题目条件重新核对判断依据。'
            result = 'incorrect'
            error_type = 'unclear'
        else:
            evaluation = '已收到你的回答，请结合本步骤提示补充选择该选项的依据。'
            result = 'unclear'
            error_type = 'unclear'
        correction = '请先梳理题目已知条件，再说明当前选项与条件之间的对应关系。'
    else:
        evaluation = '已收到你的回答，请结合当前引导问题补充关键依据。'
        result = 'unclear'
        error_type = 'unclear'
        correction = '请结合题干、图像或已知条件，补充支持你结论的关键依据。'
        key_points = step_data.get('key_points') or []
        if not isinstance(key_points, (list, tuple)):
            key_points = [key_points]
        key_points = [str(point).strip() for point in key_points if str(point).strip()]
        if key_points:
            correction += ' 可重点检查：' + '、'.join(key_points[:3]) + '。'
    return {
        'result': result,
        'error_type': error_type,
        'evaluation': evaluation,
        'correction_direction': correction,
        'next_question': None,
        'next_hint': None,
        'confidence': 0.0,
    }


def _build_guidance_answer_log(
    *, step_index, mode, user_reply, analysis_result,
    normalized_answer=None, correct_answer=None, is_correct=None,
    trace_id=None, ai_status='success', latency_ms=None,
    provider='qwen', model='qwen3.7-flash', reply_key=None, reply_id=None,
    fixed_guidance=None, failure_reason=None, failure_stage=None,
):
    entry = {
        'step': step_index,
        'mode': mode,
        'user_answer': user_reply,
        'ai_status': ai_status,
        'trace_id': trace_id,
        'provider': provider,
        'model': model,
    }
    if reply_key:
        entry['reply_key'] = reply_key
    if reply_id:
        entry['reply_id'] = reply_id
    if latency_ms is not None:
        entry['latency_ms'] = latency_ms
    if failure_reason:
        entry['failure_reason'] = failure_reason
    if failure_stage:
        entry['failure_stage'] = failure_stage
    if normalized_answer is not None:
        entry['normalized_answer'] = normalized_answer
    if correct_answer is not None and mode != 'B':
        entry['correct_answer'] = correct_answer
    if is_correct is not None and mode != 'B':
        entry['is_correct'] = is_correct
    if mode == 'B' and fixed_guidance:
        # B records the selected learning action separately.  It must not be
        # mixed with C-mode error-analysis fields in the session history.
        entry['fixed_guidance'] = fixed_guidance
        entry['action_is_correct'] = fixed_guidance.get('action_is_correct')
    elif analysis_result:
        for field_name in (
            'result', 'error_type', 'evaluation', 'correction_direction',
            'next_question', 'next_hint', 'confidence',
        ):
            entry[field_name] = analysis_result.get(field_name)
    elif mode != 'B' and ai_status != 'success':
        for field_name in (
            'result', 'error_type', 'evaluation', 'correction_direction',
            'next_question', 'next_hint', 'confidence',
        ):
            entry[field_name] = None
    return entry


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudentOnly])
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

    # C uses prepared content when available. Missing content is prepared by
    # Celery and must not make the student's start request wait for an LLM.
    questions = (ai_c or {}).get('questions') or []
    if questions:
        step_data = _extract_c_mode_step(ai_c, 0)
        return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                         'data': {
                             'session_id': session.id, 'mode': 'C',
                             'step_index': 0, 'total_steps': len(questions),
                             'hint': step_data['question'],
                             'question_info': _build_question_info(q),
                         }})
    _enqueue_guidance_preparation(q)
    fallback_step = _extract_c_mode_step({}, 0)
    log = session.content_log_json or {'step_index': 0, 'steps': [], 'answers': []}
    log['preparation_status'] = 'pending'
    session.content_log_json = log
    session.save(update_fields=['content_log_json'])
    return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                     'data': {
                         'session_id': session.id, 'mode': 'C',
                         'step_index': 0, 'total_steps': 3,
                         'hint': fallback_step['question'],
                         'is_fallback': True, 'preparation_pending': True,
                         'question_info': _build_question_info(q),
                     }})


def _guidance_processing_response(session, step_index, trace_id):
    return _response_payload({
        'mode': session.mode_type,
        'step_index': step_index,
        'processing': True,
        'retryable': True,
        'is_completed': False,
    }, trace_id)


def _reserve_guidance_reply(request, session_id, user_reply, reply_id):
    """Reserve one reply under the session row lock before calling the provider."""
    with _guidance_atomic():
        try:
            session = _guidance_model_manager().get(
                pk=session_id, student_user_id=request.user
            )
        except AIGuidanceSession.DoesNotExist:
            return Response({
                'code': 404,
                'message': 'Guidance session not found',
                'data': None,
                'trace_id': make_trace_id(),
            }, status=404)

        if session.session_status != 'running' and not (
            session.session_status == 'downgraded' and session.mode_type == 'B'
        ):
            return Response({
                'code': 4001,
                'message': 'Guidance session has ended',
                'data': None,
                'trace_id': make_trace_id(),
            }, status=400)

        log = session.content_log_json or {
            'step_index': 0, 'steps': [], 'answers': []
        }
        step_index = int(log.get('step_index', 0) or 0)
        reply_key = _guidance_reply_key(
            session.id, step_index, session.mode_type, user_reply, reply_id
        )
        existing = _find_reply_log(log, reply_key, reply_id)
        if existing:
            stored_payload = existing.get('response_data')
            if isinstance(stored_payload, dict):
                return Response(stored_payload)
            if existing.get('ai_status') == 'pending' and not _pending_reply_is_live(existing):
                existing['ai_status'] = 'abandoned'
                existing['failure_reason'] = 'stale_pending'
            else:
                return Response(_guidance_processing_response(
                    session, step_index, existing.get('trace_id') or make_trace_id()
                ))
        pending_entries = [
            entry for entry in (log.get('answers') or [])
            if entry.get('ai_status') == 'pending' and entry.get('step') == step_index
        ]
        if pending_entries and _pending_reply_is_live(pending_entries[-1]):
            return Response(_guidance_processing_response(
                session, step_index, make_trace_id()
            ))
        for pending in pending_entries:
            pending['ai_status'] = 'abandoned'
            pending['failure_reason'] = 'stale_pending'

        trace_id = make_trace_id()
        log.setdefault('answers', []).append({
            'step': step_index,
            'mode': session.mode_type,
            'user_answer': user_reply,
            'reply_key': reply_key,
            **({'reply_id': reply_id} if reply_id else {}),
            'ai_status': 'pending',
            'trace_id': trace_id,
            'provider': 'qwen',
            'model': 'qwen3.7-flash',
            'started_at': timezone.now().isoformat(),
        })
        session.content_log_json = log
        session.save(update_fields=['content_log_json'])
        return session, log, step_index, reply_key, reply_id, trace_id


def _finalize_guidance_reply(
    session_id, reply_key, entry, payload, *, next_step=None,
    mode_type=None, session_status=None, invalid_input_count=None,
):
    """Replace the pending log and advance the session atomically."""
    with _guidance_atomic():
        session = _guidance_model_manager().get(pk=session_id)
        log = session.content_log_json or {
            'step_index': 0, 'steps': [], 'answers': []
        }
        existing = _find_reply_log(log, reply_key)
        if existing and isinstance(existing.get('response_data'), dict):
            return existing['response_data']
        entry['response_data'] = payload
        _replace_reply_log(log, reply_key, entry)
        if next_step is not None:
            log['step_index'] = next_step
        session.content_log_json = log
        update_fields = ['content_log_json']
        if mode_type is not None:
            session.mode_type = mode_type
            update_fields.append('mode_type')
        if session_status is not None:
            session.session_status = session_status
            update_fields.append('session_status')
        if invalid_input_count is not None:
            session.invalid_input_count = invalid_input_count
            update_fields.append('invalid_input_count')
        session.save(update_fields=update_fields)
        return payload


def _guidance_unavailable_data(mode, step_index, total_steps, *, is_correct=None,
                               correct_answer='', analysis='', evaluation=None):
    return {
        'mode': mode,
        'step_index': step_index,
        'total_steps': total_steps,
        'is_correct': is_correct,
        'correct_answer': correct_answer if mode == 'B' else None,
        'analysis': analysis if mode == 'B' else None,
        'evaluation': evaluation or 'AI \u8BC4\u4EF7\u6682\u65F6\u4E0D\u53EF\u7528\uFF0C\u8BF7\u7A0D\u540E\u91CD\u8BD5',
        'result': None,
        'error_type': None,
        'correction_direction': None,
        'confidence': None,
        'next_question': None,
        'next_hint': None,
        'is_completed': False,
        'ai_unavailable': True,
        'retryable': True,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudentOnly])
def guidance_reply(request, session_id):
    """Process exactly one student reply with one realtime Flash evaluation."""
    user_reply = (request.data.get('reply') or '').strip()
    reply_id = str(
        request.data.get('reply_id') or request.data.get('client_reply_id') or ''
    ).strip()[:100]
    reserved = _reserve_guidance_reply(request, session_id, user_reply, reply_id)
    if isinstance(reserved, Response):
        return reserved
    session, log, step_index, reply_key, reply_id, trace_id = reserved

    try:
        q = ExamQuestion.objects.get(pk=session.question_id)
    except ExamQuestion.DoesNotExist:
        payload = {
            'code': 404, 'message': '棰樼洰涓嶅瓨鍦?', 'data': None,
            'trace_id': trace_id,
        }
        entry = _build_guidance_answer_log(
            step_index=step_index, mode=session.mode_type,
            user_reply=user_reply, analysis_result=None,
            trace_id=trace_id, ai_status='unavailable', reply_key=reply_key,
            reply_id=reply_id,
        )
        return Response(_finalize_guidance_reply(session.id, reply_key, entry, payload))

    ai_b = _as_dict(q.ai_answer_b)
    ai_c = _as_dict(q.ai_answer_c)
    mode = session.mode_type

    if mode == 'B':
        questions = (ai_b or {}).get('questions') or []
        total_steps = len(questions) or 3
        step_data = _extract_b_mode_step(ai_b, step_index)
        step_data['step_index'] = step_index
        normalized_reply = _normalize_b_option(user_reply)
        is_correct = (
            normalized_reply == step_data['correct_option']
            if step_data['correct_option'] else None
        )
    else:
        c_questions = (ai_c or {}).get('questions') or []
        if not c_questions:
            c_questions = (log.get('ai_c_generated') or {}).get('questions') or []
        total_steps = len(c_questions) or 3
        step_data = _extract_c_mode_step({'questions': c_questions}, step_index)
        normalized_reply = None
        is_correct = None

    # Invalid C input is handled deterministically and never consumes an AI call.
    if mode == 'C' and _is_invalid_reply(user_reply):
        new_invalid_count = session.invalid_input_count + 1
        if new_invalid_count >= 2:
            questions_b = (ai_b or {}).get('questions') or []
            total_steps_b = len(questions_b) or 3
            b_step = _extract_b_mode_step(ai_b, 0)
            data = {
                'mode': 'B', 'step_index': 0, 'total_steps': total_steps_b,
                'next_hint': b_step['hint'], 'options': b_step['options'],
                'downgraded': True,
                'is_completed': False,
            }
            data['downgrade_reason'] = '当前回答无效，已切换到固定选项引导模式。'
            payload = _response_payload(data, trace_id)
            entry = _build_guidance_answer_log(
                step_index=step_index, mode='C', user_reply=user_reply,
                analysis_result=None, trace_id=trace_id, ai_status='invalid',
                latency_ms=0, reply_key=reply_key, reply_id=reply_id,
            )
            committed = _finalize_guidance_reply(
                session.id, reply_key, entry, payload, next_step=0,
                mode_type='B', session_status='downgraded',
                invalid_input_count=new_invalid_count,
            )
            return Response(committed)
        data = {
            'mode': 'C', 'step_index': step_index, 'total_steps': total_steps,
            'evaluation': '请用一句话说明你的思路，再继续下一步。',
            'result': 'unclear', 'error_type': 'unclear',
            'correction_direction': '请补充与当前引导问题直接相关的解题依据。',
            'confidence': 0.0, 'next_question': step_data['question'],
            'next_hint': step_data['question'], 'is_completed': False,
            'retryable': True,
        }
        payload = _response_payload(data, trace_id)
        entry = _build_guidance_answer_log(
            step_index=step_index, mode='C', user_reply=user_reply,
            analysis_result=None, trace_id=trace_id, ai_status='invalid',
            latency_ms=0, reply_key=reply_key, reply_id=reply_id,
        )
        committed = _finalize_guidance_reply(
            session.id, reply_key, entry, payload,
            invalid_input_count=new_invalid_count,
        )
        return Response(committed)

    # B is a fixed learning-action flow.  It does not need realtime AI for a
    # selection-only reply; keeping it available also makes the fallback path
    # fast and independent of the AI gray switch.
    if mode != 'B' and not _guidance_ai_enabled(request.user):
        data = _guidance_unavailable_data(
            mode, step_index, total_steps, is_correct=is_correct,
            correct_answer=step_data.get('correct_option', ''),
            analysis=step_data.get('analysis', ''),
            evaluation='AI 引导暂时关闭，请稍后重试。',
        )
        payload = _response_payload(data, trace_id)
        entry = _build_guidance_answer_log(
            step_index=step_index, mode=mode, user_reply=user_reply,
            analysis_result=None, normalized_answer=normalized_reply,
            correct_answer=step_data.get('correct_option') if mode == 'B' else None,
            is_correct=is_correct if mode == 'B' else None,
            trace_id=trace_id, ai_status='disabled', latency_ms=0,
            reply_key=reply_key, reply_id=reply_id,
        )
        committed = _finalize_guidance_reply(session.id, reply_key, entry, payload)
        return Response(committed)

    started_at = time.perf_counter()
    failure_reason = None
    failure_stage = None
    ai_status = 'success'
    ai_degraded = False
    if mode == 'B':
        # A fixed option is still evaluated once by Flash, but through a
        # dedicated prompt/schema that analyzes the selected learning action.
        # It never uses the C-mode answer/error-analysis evaluator.
        analysis_result = None
        ai_status = 'deterministic'
        try:
            analysis_result = _normalize_fixed_guidance_result(
                guidance_component_factory().evaluate_fixed_guidance_reply(
                    _build_guidance_context(
                        q=q,
                        mode='B',
                        step_data=step_data,
                        user_reply=user_reply,
                        log=log,
                        trace_id=trace_id,
                        program_is_correct=is_correct,
                    )
                )
            )
            ai_status = 'success'
        except AIResponseError as error:
            logger.warning('Fixed guidance AI response format invalid; using safe fallback', extra={
                'trace_id': trace_id, 'mode': 'B',
            })
            failure_reason = type(error).__name__
            failure_stage = 'response'
            ai_status = 'fallback'
            ai_degraded = True
        except AIConfigError as error:
            logger.exception('Fixed guidance AI configuration failed')
            failure_reason = type(error).__name__
            failure_stage = 'config'
            ai_status = 'fallback'
            ai_degraded = True
        except AIRequestError as error:
            logger.warning('Fixed guidance AI provider request failed', extra={
                'trace_id': trace_id, 'mode': 'B',
            })
            failure_reason = type(error).__name__
            failure_stage = 'request'
            ai_status = 'fallback'
            ai_degraded = True
        except Exception as error:
            logger.exception('Fixed guidance AI evaluation failed')
            failure_reason = type(error).__name__
            failure_stage = 'unknown'
            ai_status = 'fallback'
            ai_degraded = True
    else:
        try:
            context_log = dict(log)
            context_log['answers'] = [
                entry for entry in (log.get('answers') or [])
                if entry.get('reply_key') != reply_key
            ]
            raw_analysis = guidance_component_factory().evaluate_student_reply(
                _build_guidance_context(
                    q=q, mode=mode, step_data=step_data, user_reply=user_reply,
                    log=context_log, trace_id=trace_id,
                    program_is_correct=None,
                )
            )
            analysis_result = _normalize_guidance_result(raw_analysis)
        except AIResponseError as error:
            # The model call has already happened. Recover only from a malformed
            # response; never retry or infer a specific C-mode error without evidence.
            logger.warning('Student guidance evaluation response format invalid; using safe fallback', extra={
                'trace_id': trace_id, 'mode': mode,
            })
            failure_reason = type(error).__name__
            ai_status = 'fallback'
            ai_degraded = True
            analysis_result = _build_guidance_format_fallback(
                mode, step_data, is_correct=None,
            )
        except AIConfigError as error:
            logger.exception('Student guidance evaluation configuration failed')
            failure_reason = type(error).__name__
            analysis_result = None
        except Exception as error:
            logger.exception('Student guidance evaluation failed')
            failure_reason = type(error).__name__
            analysis_result = None

    latency_ms = round((time.perf_counter() - started_at) * 1000)

    # B-mode has its own response contract.  A fixed option is a learning
    # action, so it must not be represented by C-mode evaluation fields such
    # as error_type/correction_direction, and it must not expose the original
    # question answer or analysis as if the student had answered the question.
    if mode == 'B':
        next_step = step_index + 1
        is_completed = next_step >= total_steps
        next_data = (
            _extract_b_mode_step(ai_b, next_step)
            if not is_completed else {}
        )
        next_data['step_index'] = next_step

        # Never synthesize a topic-specific branch in the view.  The next
        # prompt must come from the current AI evaluation or from the next
        # prepared B step, and the prepared fallback must not be used as a
        # question when it has no question-specific content.
        next_question = None
        next_hint = None
        if analysis_result:
            next_question = (
                analysis_result.get('next_question')
                or analysis_result.get('next_hint')
            )
            next_hint = analysis_result.get('next_hint') or next_question
        if not next_question and not next_data.get('is_fallback'):
            next_question = next_data.get('hint') or None
            next_hint = next_question

        # A provider failure or malformed response must not advance the B
        # session.  Returning an unavailable payload also prevents the client
        # from appending a stale/fallback next question to the conversation.
        if analysis_result is None:
            fixed_guidance = _build_fixed_guidance_selection_result(
                step_data,
                normalized_reply,
                is_correct=is_correct,
            )['fixed_guidance']
            fixed_guidance['ai_status'] = ai_status
            fixed_guidance['failure_stage'] = failure_stage
            fixed_guidance['current_step'] = {
                'index': step_index,
                'question': step_data.get('question') or step_data.get('hint') or '',
                'options': list(step_data.get('options') or []),
            }
            fixed_guidance['next_step'] = None
            data = _guidance_unavailable_data(
                'B', step_index, total_steps, is_correct=is_correct,
                evaluation='本次固定引导评价暂时不可用，请稍后重试。',
            )
            for field_name in (
                'correct_answer', 'analysis', 'result', 'error_type',
                'correction_direction',
            ):
                data.pop(field_name, None)
            data.update({
                'fixed_guidance': fixed_guidance,
                'ai_degraded': True,
                'ai_status': ai_status,
                'ai_failure_stage': failure_stage,
            })
            payload = _response_payload(data, trace_id)
            entry = _build_guidance_answer_log(
                step_index=step_index,
                mode='B',
                user_reply=user_reply,
                analysis_result=None,
                normalized_answer=normalized_reply,
                is_correct=is_correct,
                trace_id=trace_id,
                ai_status=ai_status,
                latency_ms=latency_ms,
                reply_key=reply_key,
                reply_id=reply_id,
                fixed_guidance=fixed_guidance,
                failure_reason=failure_reason,
                failure_stage=failure_stage,
            )
            committed = _finalize_guidance_reply(
                session.id, reply_key, entry, payload
            )
            return Response(committed)

        fixed_guidance = _build_fixed_guidance_selection_result(
            step_data,
            normalized_reply,
            is_correct=is_correct,
            next_data=next_data,
            next_question=next_question,
            next_hint=next_hint,
        )['fixed_guidance']
        fixed_guidance['feedback'] = analysis_result['feedback']
        fixed_guidance['known_information'] = analysis_result['known_information']
        fixed_guidance['guidance'] = analysis_result['guidance']
        fixed_guidance['ai_confidence'] = analysis_result['confidence']
        if failure_stage:
            fixed_guidance['failure_stage'] = failure_stage
        fixed_guidance['ai_status'] = ai_status
        fixed_guidance['current_step'] = {
            'index': step_index,
            'question': step_data.get('question') or step_data.get('hint') or '',
            'options': list(step_data.get('options') or []),
        }
        if is_completed or not next_question:
            fixed_guidance['next_step'] = None
        else:
            fixed_guidance['next_step'] = {
                'index': next_step,
                'question': fixed_guidance['next_question'],
                'hint': fixed_guidance['next_hint'],
                'options': fixed_guidance['next_options'],
            }
        data = {
            'mode': 'B',
            'step_index': next_step if is_completed or next_question else step_index,
            'total_steps': total_steps,
            'is_completed': is_completed,
            'fixed_guidance': fixed_guidance,
            # Compatibility aliases for clients that still read the old
            # navigation fields.  The UI uses fixed_guidance exclusively.
            'next_question': (
                fixed_guidance['next_question'] if not is_completed and next_question else None
            ),
            'next_hint': (
                fixed_guidance['next_hint'] if not is_completed and next_question else None
            ),
            'options': (
                fixed_guidance['next_options'] if not is_completed and next_question else []
            ),
            'ai_degraded': ai_degraded,
            'ai_status': ai_status,
            'ai_failure_stage': failure_stage,
            'retryable': bool(not is_completed and not next_question),
        }
        payload = _response_payload(data, trace_id)
        entry = _build_guidance_answer_log(
            step_index=step_index,
            mode='B',
            user_reply=user_reply,
            analysis_result=None,
            normalized_answer=normalized_reply,
            is_correct=is_correct,
            trace_id=trace_id,
            ai_status=ai_status,
            latency_ms=latency_ms,
            reply_key=reply_key,
            reply_id=reply_id,
            fixed_guidance=fixed_guidance,
            failure_reason=failure_reason,
            failure_stage=failure_stage,
        )
        committed = _finalize_guidance_reply(
            session.id,
            reply_key,
            entry,
            payload,
            next_step=next_step if is_completed or next_question else None,
            session_status='completed' if is_completed else None,
        )
        logger.info('student_guidance_reply_completed', extra={
            'trace_id': trace_id,
            'mode': 'B',
            'latency_ms': latency_ms,
            'step_index': step_index,
            'ai_status': ai_status,
            'failure_stage': failure_stage,
        })
        return Response(committed)

    if analysis_result is None:
        data = _guidance_unavailable_data(
            mode, step_index, total_steps, is_correct=is_correct,
            correct_answer=step_data.get('correct_option', ''),
            analysis=step_data.get('analysis', ''),
        )
        payload = _response_payload(data, trace_id)
        entry = _build_guidance_answer_log(
            step_index=step_index, mode=mode, user_reply=user_reply,
            analysis_result=None, normalized_answer=normalized_reply,
            correct_answer=step_data.get('correct_option') if mode == 'B' else None,
            is_correct=is_correct if mode == 'B' else None,
            trace_id=trace_id, ai_status='unavailable', latency_ms=latency_ms,
            reply_key=reply_key, reply_id=reply_id,
        )
        if failure_reason:
            entry['failure_reason'] = failure_reason
        committed = _finalize_guidance_reply(session.id, reply_key, entry, payload)
        return Response(committed)

    evaluation = analysis_result['evaluation']
    next_step = step_index + 1
    is_completed = next_step >= total_steps
    next_question = analysis_result.get('next_question')
    next_hint = analysis_result.get('next_hint')
    if not is_completed:
        # B has returned through its dedicated branch above.  This remaining
        # path is C-only and keeps the free-answer AI response contract intact.
        next_data = _extract_c_mode_step({'questions': c_questions}, next_step)
        next_question = next_question or next_data['question']
        next_hint = next_hint or next_question
        data = {
            'mode': 'C', 'step_index': next_step, 'total_steps': total_steps,
            'evaluation': evaluation, 'result': analysis_result['result'],
            'error_type': analysis_result['error_type'],
            'correction_direction': analysis_result['correction_direction'],
            'confidence': analysis_result['confidence'],
            'next_question': next_question, 'next_hint': next_hint,
            'ai_degraded': ai_degraded,
            'is_completed': False,
        }
        payload = _response_payload(data, trace_id)
        entry = _build_guidance_answer_log(
            step_index=step_index, mode=mode, user_reply=user_reply,
            analysis_result=analysis_result, normalized_answer=normalized_reply,
            correct_answer=step_data.get('correct_option') if mode == 'B' else None,
            is_correct=is_correct if mode == 'B' else None,
            trace_id=trace_id, ai_status=ai_status, latency_ms=latency_ms,
            reply_key=reply_key, reply_id=reply_id,
        )
        if failure_reason:
            entry['failure_reason'] = failure_reason
        committed = _finalize_guidance_reply(
            session.id, reply_key, entry, payload, next_step=next_step
        )
        logger.info('student_guidance_reply_completed', extra={
            'trace_id': trace_id, 'mode': mode, 'latency_ms': latency_ms,
            'step_index': step_index, 'result': analysis_result['result'],
        })
        return Response(committed)

    summary = (ai_c or {}).get('summary', '')
    final_answer = (ai_c or {}).get('final_answer', '')
    data = {
        'mode': mode, 'step_index': next_step, 'total_steps': total_steps,
        'is_completed': True, 'summary': summary, 'final_answer': final_answer,
        'evaluation': evaluation, 'result': analysis_result['result'],
        'error_type': analysis_result['error_type'],
        'correction_direction': analysis_result['correction_direction'],
        'confidence': analysis_result['confidence'],
        'next_question': next_question, 'next_hint': next_hint,
        'ai_degraded': ai_degraded,
    }
    payload = _response_payload(data, trace_id)
    entry = _build_guidance_answer_log(
        step_index=step_index, mode=mode, user_reply=user_reply,
        analysis_result=analysis_result, normalized_answer=normalized_reply,
        correct_answer=step_data.get('correct_option') if mode == 'B' else None,
        is_correct=is_correct if mode == 'B' else None,
        trace_id=trace_id, ai_status=ai_status, latency_ms=latency_ms,
        reply_key=reply_key, reply_id=reply_id,
    )
    if failure_reason:
        entry['failure_reason'] = failure_reason
    committed = _finalize_guidance_reply(
        session.id, reply_key, entry, payload, next_step=next_step,
        session_status='completed',
    )
    logger.info('student_guidance_reply_completed', extra={
        'trace_id': trace_id, 'mode': mode, 'latency_ms': latency_ms,
        'step_index': step_index, 'result': analysis_result['result'],
    })
    return Response(committed)

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
    _enqueue_guidance_preparation(q)
    fallback_step = _extract_c_mode_step({}, 0)
    log = session.content_log_json or {'step_index': 0, 'steps': [], 'answers': []}
    log['preparation_status'] = 'pending'
    session.content_log_json = log
    session.save(update_fields=['content_log_json'])
    return Response({'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
                     'data': {
                         'session_id': session.id, 'mode': 'C',
                         'step_index': 0, 'total_steps': 3,
                         'hint': fallback_step['question'],
                         'is_fallback': True,
                         'preparation_pending': True,
                         'question_info': _build_question_info(q),
                     }})

    try:
        generated = guidance_component_factory().generate(
            QuestionInput(stem=q.stem or '', answer=q.answer or '')
        )
        if generated and generated.get('steps'):
            llm_steps = generated['steps']
            total_steps = len(llm_steps)
            # 将 steps 转成 questions 格式，存入 session 供后续 guidance_reply 使用
            converted_questions = []
            for step in llm_steps:
                converted_questions.append({
                    'question': step['question'],
                    'reference_answer': step['hint'],
                    'key_points': [],
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
@permission_classes([IsAuthenticated, IsStudentOnly])
def _legacy_guidance_reply(request, session_id):
    """S-07: 推进引导（B 模式分步判断 + C 模式 LLM 评价 + 步进）。"""
    try:
        session = AIGuidanceSession.objects.get(pk=session_id, student_user_id=request.user)
    except AIGuidanceSession.DoesNotExist:
        return Response({'code': 404, 'message': '引导会话不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)
    # C 模式无法生成开放式引导时会降级为 B 模式。降级会话仍可继续完成
    # 固定选项引导，不能因为状态标记为 downgraded 而被误判为已结束。
    if session.session_status != 'running' and not (
        session.session_status == 'downgraded' and session.mode_type == 'B'
    ):
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
    analysis_result = None

    # C→B 降级（连续无效输入）
    if session.mode_type == 'C' and _is_invalid_reply(user_reply):
        session.invalid_input_count += 1
        if session.invalid_input_count >= 2:
            session.mode_type = 'B'
            session.session_status = 'downgraded'
            log['step_index'] = 0
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
        normalized_reply = _normalize_b_option(user_reply)
        # 兜底时 correct_option 为空，跳过正确性判断
        is_correct = None
        if step_data['correct_option']:
            is_correct = normalized_reply == step_data['correct_option']
        current_step_data = step_data

    if session.mode_type == 'B':
        trace_id = make_trace_id()
        started_at = time.perf_counter()
        try:
            raw_analysis = guidance_component_factory().evaluate_student_reply(
                _build_guidance_context(
                    q=q,
                    mode='B',
                    step_data=current_step_data,
                    user_reply=user_reply,
                    log=log,
                    trace_id=trace_id,
                    program_is_correct=is_correct,
                )
            )
            analysis_result = _normalize_guidance_result(raw_analysis)
            if is_correct is True:
                analysis_result['result'] = 'correct'
                analysis_result['error_type'] = None
            elif is_correct is False:
                analysis_result['result'] = 'incorrect'
        except AIConfigError:
            logger.exception('Student guidance B evaluation configuration failed')
            log.setdefault('answers', []).append({
                'step': step_index,
                'mode': 'B',
                'user_answer': user_reply,
                'normalized_answer': normalized_reply,
                'correct_answer': step_data['correct_option'],
                'is_correct': is_correct,
                'ai_status': 'unavailable',
                'trace_id': trace_id,
                'provider': 'qwen',
                'model': 'qwen3.7-flash',
                'latency_ms': round((time.perf_counter() - started_at) * 1000),
                'result': None,
                'error_type': None,
                'evaluation': None,
                'correction_direction': None,
                'next_question': None,
                'next_hint': None,
                'confidence': None,
            })
            session.content_log_json = log
            session.save(update_fields=['content_log_json'])
            return Response({'code': 0, 'message': 'success', 'trace_id': trace_id,
                             'data': {
                                 'mode': 'B', 'step_index': step_index,
                                 'total_steps': total_steps,
                                 'is_correct': is_correct,
                                 'correct_answer': step_data['correct_option'],
                                 'analysis': step_data['analysis'],
                                 'evaluation': 'AI 评价暂时不可用，请稍后重试',
                                 'result': None,
                                 'error_type': None,
                                 'correction_direction': None,
                                 'confidence': None,
                                 'next_question': None,
                                 'next_hint': None,
                                 'is_completed': False,
                                 'ai_unavailable': True,
                                 'retryable': True,
                             }})
        except Exception:
            logger.exception('Student guidance B evaluation failed')
            log.setdefault('answers', []).append({
                'step': step_index,
                'mode': 'B',
                'user_answer': user_reply,
                'normalized_answer': normalized_reply,
                'correct_answer': step_data['correct_option'],
                'is_correct': is_correct,
                'ai_status': 'unavailable',
                'trace_id': trace_id,
                'provider': 'qwen',
                'model': 'qwen3.7-flash',
                'latency_ms': round((time.perf_counter() - started_at) * 1000),
                'result': None,
                'error_type': None,
                'evaluation': None,
                'correction_direction': None,
                'next_question': None,
                'next_hint': None,
                'confidence': None,
            })
            session.content_log_json = log
            session.save(update_fields=['content_log_json'])
            return Response({'code': 0, 'message': 'success', 'trace_id': trace_id,
                             'data': {
                                 'mode': 'B', 'step_index': step_index,
                                 'total_steps': total_steps,
                                 'is_correct': is_correct,
                                 'correct_answer': step_data['correct_option'],
                                 'analysis': step_data['analysis'],
                                 'evaluation': 'AI 评价暂时不可用，请稍后重试',
                                 'result': None,
                                 'error_type': None,
                                 'correction_direction': None,
                                 'confidence': None,
                                 'next_question': None,
                                 'next_hint': None,
                                 'is_completed': False,
                                 'ai_unavailable': True,
                                 'retryable': True,
                             }})
        log.setdefault('answers', []).append(
            _build_guidance_answer_log(
                step_index=step_index,
                mode='B',
                user_reply=user_reply,
                analysis_result=analysis_result,
                normalized_answer=normalized_reply,
                correct_answer=step_data['correct_option'],
                is_correct=is_correct,
                trace_id=trace_id,
                latency_ms=round((time.perf_counter() - started_at) * 1000),
            )
        )

    if session.mode_type == 'C':
        # 优先从 ai_answer_c 读取，若为空则尝试从 session 的 content_log_json 读取 LLM 实时生成的数据
        c_questions = (ai_c or {}).get('questions') or []
        if not c_questions:
            c_questions = (log.get('ai_c_generated') or {}).get('questions') or []
        total_steps = len(c_questions) or 3
        current_step_data = _extract_c_mode_step(
            {'questions': c_questions}, step_index
        )
        trace_id = make_trace_id()
        started_at = time.perf_counter()
        # 调用 LLM 进行评价；失败时保留当前步骤，不推进。
        try:
            raw_analysis = guidance_component_factory().evaluate_student_reply(
                _build_guidance_context(
                    q=q,
                    mode='C',
                    step_data=current_step_data,
                    user_reply=user_reply,
                    log=log,
                    trace_id=trace_id,
                )
            )
            analysis_result = _normalize_guidance_result(raw_analysis)
            evaluation = analysis_result['evaluation']
        except AIConfigError:
            logger.exception('Student guidance evaluation configuration failed')
            evaluation = 'AI 评价暂时不可用，请稍后重试'
            log.setdefault('answers', []).append(
                _build_guidance_answer_log(
                    step_index=step_index,
                    mode='C',
                    user_reply=user_reply,
                    analysis_result=None,
                    trace_id=trace_id,
                    ai_status='unavailable',
                    latency_ms=round((time.perf_counter() - started_at) * 1000),
                )
            )
            session.content_log_json = log
            session.save(update_fields=['content_log_json'])
            return Response({'code': 0, 'message': 'success', 'trace_id': trace_id,
                             'data': {
                                 'mode': 'C', 'step_index': step_index,
                                 'total_steps': total_steps,
                                 'evaluation': evaluation,
                                 'result': None,
                                 'error_type': None,
                                 'correction_direction': None,
                                 'confidence': None,
                                 'next_question': None,
                                 'next_hint': None,
                                 'is_completed': False,
                                 'ai_unavailable': True,
                                 'retryable': True,
                             }})
        except Exception:
            logger.exception('Student guidance evaluation failed')
            evaluation = 'AI 评价暂时不可用，请稍后重试'
            log.setdefault('answers', []).append(
                _build_guidance_answer_log(
                    step_index=step_index,
                    mode='C',
                    user_reply=user_reply,
                    analysis_result=None,
                    trace_id=trace_id,
                    ai_status='unavailable',
                    latency_ms=round((time.perf_counter() - started_at) * 1000),
                )
            )
            session.content_log_json = log
            session.save(update_fields=['content_log_json'])
            return Response({'code': 0, 'message': 'success', 'trace_id': trace_id,
                             'data': {
                                 'mode': 'C', 'step_index': step_index,
                                 'total_steps': total_steps,
                                 'evaluation': evaluation,
                                 'result': None,
                                 'error_type': None,
                                 'correction_direction': None,
                                 'confidence': None,
                                 'next_question': None,
                                 'next_hint': None,
                                 'is_completed': False,
                                 'ai_unavailable': True,
                                 'retryable': True,
                             }})
        log.setdefault('answers', []).append(
            _build_guidance_answer_log(
                step_index=step_index,
                mode='C',
                user_reply=user_reply,
                analysis_result=analysis_result,
                trace_id=trace_id,
                latency_ms=round((time.perf_counter() - started_at) * 1000),
            )
        )

    # 推进到下一步
    next_step = step_index + 1
    log['step_index'] = next_step
    is_completed = next_step >= total_steps

    # 未完成 → 返回下一步数据
    if not is_completed:
        if session.mode_type == 'B':
            next_data = _extract_b_mode_step(ai_b, next_step)
            next_question = analysis_result.get('next_question') or next_data['hint']
            next_hint = analysis_result.get('next_hint') or next_question
            session.content_log_json = log
            session.save()
            return Response({'code': 0, 'message': 'success', 'trace_id': trace_id,
                             'data': {
                                 'mode': 'B', 'step_index': next_step, 'total_steps': total_steps,
                                 'is_correct': is_correct,
                                 'correct_answer': step_data['correct_option'],
                                 'analysis': step_data['analysis'],
                                 'evaluation': analysis_result['evaluation'],
                                 'result': analysis_result['result'],
                                 'error_type': analysis_result['error_type'],
                                 'correction_direction': analysis_result['correction_direction'],
                                 'confidence': analysis_result['confidence'],
                                 'next_question': next_question,
                                 'next_hint': next_hint,
                                 'options': next_data['options'],
                                 'is_completed': False,
                             }})
        else:
            next_data = _extract_c_mode_step({'questions': c_questions}, next_step)
            next_question = analysis_result.get('next_question') or next_data['question']
            next_hint = analysis_result.get('next_hint') or next_question
            session.content_log_json = log
            session.save()
            return Response({'code': 0, 'message': 'success', 'trace_id': trace_id,
                             'data': {
                                 'mode': 'C', 'step_index': next_step, 'total_steps': total_steps,
                                 'evaluation': evaluation,
                                 'result': analysis_result['result'],
                                 'error_type': analysis_result['error_type'],
                                 'correction_direction': analysis_result['correction_direction'],
                                 'confidence': analysis_result['confidence'],
                                 'next_question': next_question,
                                 'next_hint': next_hint,
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

    next_question = analysis_result.get('next_question') if analysis_result else None
    next_hint = analysis_result.get('next_hint') if analysis_result else None
    return Response({'code': 0, 'message': 'success', 'trace_id': trace_id,
                     'data': {
                         'mode': session.mode_type,
                         'step_index': next_step, 'total_steps': total_steps,
                         'is_completed': True,
                         'summary': summary,
                         'final_answer': final_answer,
                         'is_correct': is_correct if session.mode_type == 'B' else None,
                         'correct_answer': step_data.get('correct_option', '') if session.mode_type == 'B' else None,
                         'analysis': step_data.get('analysis', '') if session.mode_type == 'B' else None,
                         'evaluation': analysis_result.get('evaluation') if analysis_result else evaluation,
                         'result': analysis_result.get('result') if analysis_result else None,
                         'error_type': analysis_result.get('error_type') if analysis_result else None,
                         'correction_direction': analysis_result.get('correction_direction') if analysis_result else None,
                         'confidence': analysis_result.get('confidence') if analysis_result else None,
                         'next_question': next_question,
                         'next_hint': next_hint,
                     }})
