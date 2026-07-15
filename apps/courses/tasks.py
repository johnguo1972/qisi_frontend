"""Celery tasks for variant question generation."""
import json
import logging
import time
from celery import shared_task
from django.utils import timezone

from apps.courses.models import VariantTask, CourseQuestionLink
from apps.courses.prompts import (
    VARIANT_SYSTEM_PROMPT,
    VERIFIER_SYSTEM_PROMPT,
    build_variant_user_prompt,
    build_verifier_user_prompt,
)
from apps.courses.validator import VariantValidator
from apps.courses.ai_service import call_ai, parse_json_response
from apps.parser.models import ExamQuestion, QuestionOption

logger = logging.getLogger(__name__)


def _get_ai_model(model_key: str) -> str:
    """从环境变量获取 AI 模型名称。"""
    import os
    model_map = {
        'qwen3.6-flash': os.environ.get('AI_MODEL_QWEN_36_FLASH', 'qwen3.6-flash'),
        'qwen3.6-plus': os.environ.get('AI_MODEL_QWEN_36_PLUS', 'qwen3.6-plus'),
        'qwen3.7-flash': os.environ.get('AI_MODEL_QWEN_37_FLASH', 'qwen3.7-flash'),
        'qwen3.7-plus': os.environ.get('AI_MODEL_QWEN_37_PLUS', 'qwen3.7-plus'),
        'deepseek': os.environ.get('DEEPSEEK_MODEL', 'deepseek-v4-pro'),
    }
    return model_map.get(model_key, model_key)


def _build_question_data(question: ExamQuestion) -> dict:
    """从 ExamQuestion 构建 AI 所需的题目数据。"""
    data = {
        'stem': question.stem or '',
        'question_type': question.question_type or 'unknown',
        'answer': question.answer or '',
        'analysis': question.analysis or '',
        'solution': question.solution or '',
        'difficulty': float(question.difficulty) if question.difficulty else 3,
        'knowledge_points': question.knowledge_points or [],
    }

    # 获取选项
    options = list(question.options.order_by('sort_order'))
    if options:
        data['options'] = [
            {'label': opt.option_label, 'content': opt.content}
            for opt in options
        ]

    return data


def _save_variant_as_question(variant_task: VariantTask, variant_data: dict) -> ExamQuestion:
    """将生成的变式题保存为 ExamQuestion 记录，并建立课程关联。"""
    from django.conf import settings

    original = variant_task.original_question

    # 创建 ExamQuestion 记录
    variant_q = ExamQuestion.objects.create(
        paper=original.paper,
        question_no=f"VAR-{variant_task.id}",
        question_type=variant_data.get('question_type', original.question_type),
        subject=original.subject,
        stem=variant_data.get('stem', ''),
        answer=variant_data.get('answer', ''),
        analysis=variant_data.get('analysis', ''),
        solution=variant_data.get('solution', ''),
        difficulty=variant_data.get('difficulty', original.difficulty),
        knowledge_points=variant_data.get('knowledge_points', original.knowledge_points),
        original_question=original,
        confidence=0.8,
        need_review=True,
        review_status='need_review',
        parse_status='auto_parsed',
    )

    # 保存选项（如果是选择题）
    options = variant_data.get('options', [])
    if options and isinstance(options, list):
        for idx, opt in enumerate(options):
            if isinstance(opt, dict):
                QuestionOption.objects.create(
                    question=variant_q,
                    option_label=opt.get('label', ''),
                    content=opt.get('content', ''),
                    sort_order=idx,
                )

    # 如果变式题关联了课程树节点，建立习题关联
    if variant_task.generated_question and variant_task.generated_question.get('tree_node_id'):
        tree_node_id = variant_task.generated_question['tree_node_id']
        from apps.courses.models import CourseTree
        try:
            tree_node = CourseTree.objects.get(id=tree_node_id)
            CourseQuestionLink.objects.get_or_create(
                course=tree_node.course,
                question=variant_q,
                defaults={
                    'tree_node': tree_node,
                    'source': 'generated',
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create course question link: {e}")

    return variant_q


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_variant_task(self, question_id: int, variant_mode: str,
                           tree_node_id: int = None) -> dict:
    """Celery 异步任务：基于原题生成变式题。

    流程：
    1. 获取原题
    2. 创建 VariantTask 记录
    3. 完整性检查
    4. 调用 qwen3.7-plus 生成变式题
    5. 程序校验（VariantValidator）
    6. DeepSeek 校验器验证
    7. 保存 ExamQuestion (review_status='need_review')

    Args:
        question_id: 原题 ID
        variant_mode: 变式模式（如 "数值变化"、"情境变化"）
        tree_node_id: 课程树节点 ID（可选）
    """
    logger.info(f"[VariantTask] Starting: question_id={question_id}, mode={variant_mode}")

    # 1. 获取原题
    try:
        original = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        raise ValueError(f"Original question not found: {question_id}")

    # 2. 创建 VariantTask
    variant_task = VariantTask.objects.create(
        original_question=original,
        variant_mode=variant_mode,
        status='running',
    )

    try:
        # 3. 构建原题数据
        question_data = _build_question_data(original)

        # 完整性检查
        if not question_data.get('stem'):
            raise ValueError("原题题干为空，无法生成变式题")

        variant_task.generator_result = {'status': 'data_prepared', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')}
        variant_task.save(update_fields=['generator_result'])

        # 4. 调用 qwen3.7-plus 生成变式题
        logger.info(f"[VariantTask] Calling qwen3.7-plus for generation...")
        qwen_model = _get_ai_model('qwen3.7-plus')
        user_prompt = build_variant_user_prompt(question_data, variant_mode)

        generator_start = time.time()
        raw_response = call_ai(
            system_prompt=VARIANT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=qwen_model,
            max_tokens=8000,
            temperature=0.1,
        )
        generation_time_ms = int((time.time() - generator_start) * 1000)

        try:
            variant_data = parse_json_response(raw_response)
        except ValueError as e:
            raise ValueError(f"AI 生成结果 JSON 解析失败: {e}")

        logger.info(f"[VariantTask] Generation complete in {generation_time_ms}ms")
        variant_task.generator_result = {
            'status': 'generated',
            'model': qwen_model,
            'latency_ms': generation_time_ms,
            'raw_response': raw_response[:2000],
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        variant_task.save(update_fields=['generator_result'])

        # 5. 程序校验
        validator = VariantValidator()
        validation_issues = validator.validate(variant_data, original)

        if validation_issues:
            logger.warning(f"[VariantTask] Validation issues: {validation_issues}")
            # 校验失败，重试一次
            if self.request.retries == 0:
                variant_task.generator_result['validation_issues'] = validation_issues
                variant_task.save(update_fields=['generator_result'])
                logger.info(f"[VariantTask] Retrying after validation failure (attempt {self.request.retries + 1})")
                self.retry(countdown=15)
            else:
                # 重试后仍然失败，记录错误
                raise ValueError(f"变式题校验不通过: {', '.join(validation_issues)}")

        # 6. DeepSeek 校验器验证
        logger.info(f"[VariantTask] Calling DeepSeek verifier...")
        deepseek_model = _get_ai_model('deepseek')
        verifier_prompt = build_verifier_user_prompt(variant_data, question_data)

        verifier_start = time.time()
        try:
            verifier_api_key = None
            from apps.courses.ai_service import get_deepseek_api_key
            verifier_api_key = get_deepseek_api_key()
        except ValueError:
            logger.warning("[VariantTask] DeepSeek API key not configured, skipping AI verification")

        verifier_result = None
        if verifier_api_key:
            try:
                raw_verifier = call_ai(
                    system_prompt=VERIFIER_SYSTEM_PROMPT,
                    user_prompt=verifier_prompt,
                    model=deepseek_model,
                    api_url="https://api.deepseek.com/v1/chat/completions",
                    api_key=verifier_api_key,
                    max_tokens=2000,
                    temperature=0.1,
                )
                verifier_time_ms = int((time.time() - verifier_start) * 1000)
                verifier_result = parse_json_response(raw_verifier)
                verifier_result['latency_ms'] = verifier_time_ms
                verifier_result['model'] = deepseek_model

                logger.info(f"[VariantTask] Verifier result: passed={verifier_result.get('passed')}, "
                           f"score={verifier_result.get('score')}")

                # 如果 DeepSeek 校验不通过且无重试次数，记录问题
                if not verifier_result.get('passed') and self.request.retries == 0:
                    variant_task.verifier_result = verifier_result
                    variant_task.save(update_fields=['verifier_result', 'generated_question'])
                    self.retry(countdown=15)

            except Exception as e:
                logger.warning(f"[VariantTask] DeepSeek verification failed: {e}")
                verifier_result = {'error': str(e), 'model': deepseek_model}

        variant_task.verifier_result = verifier_result
        variant_task.generated_question = variant_data
        variant_task.status = 'success'
        variant_task.completed_at = timezone.now()
        variant_task.save(update_fields=['verifier_result', 'generated_question', 'status', 'completed_at'])

        # 7. 保存为 ExamQuestion
        try:
            variant_q = _save_variant_as_question(variant_task, variant_data)
            logger.info(f"[VariantTask] Saved as ExamQuestion id={variant_q.id}")
            return {
                'status': 'success',
                'variant_task_id': variant_task.id,
                'question_id': variant_q.id,
            }
        except Exception as e:
            logger.error(f"[VariantTask] Failed to save variant as question: {e}")
            variant_task.status = 'failed'
            variant_task.error_message = f"保存变式题失败: {e}"
            variant_task.save(update_fields=['status', 'error_message'])
            self.retry(countdown=30)

    except Exception as e:
        logger.exception(f"[VariantTask] Task failed for question_id={question_id}")
        variant_task.status = 'failed'
        variant_task.error_message = str(e)
        variant_task.completed_at = timezone.now()
        variant_task.save(update_fields=['status', 'error_message', 'completed_at'])
        self.retry(exc=e, countdown=30 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=1, default_retry_delay=15)
def batch_generate_variants_task(self, question_ids: list, variant_mode: str,
                                  tree_node_id: int = None) -> dict:
    """批量生成变式题：为每个题目分发独立的 generate_variant_task。

    Args:
        question_ids: 原题 ID 列表
        variant_mode: 变式模式
        tree_node_id: 课程树节点 ID（可选）

    Returns:
        {'task_ids': [...], 'count': N}
    """
    logger.info(f"[BatchVariantTask] Starting: {len(question_ids)} questions, mode={variant_mode}")

    task_ids = []
    for qid in question_ids:
        try:
            result = generate_variant_task.delay(
                question_id=qid,
                variant_mode=variant_mode,
                tree_node_id=tree_node_id,
            )
            task_ids.append(result.id)
            logger.info(f"[BatchVariantTask] Dispatched task for question_id={qid}, celery_id={result.id}")
        except Exception as e:
            logger.error(f"[BatchVariantTask] Failed to dispatch for question_id={qid}: {e}")

    return {'task_ids': task_ids, 'count': len(task_ids)}
