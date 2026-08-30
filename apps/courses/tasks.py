"""Celery tasks for course features."""
import logging
import os
import time
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.courses import convert_service
from apps.courses.models import CourseMaterial, VariantTask, CourseQuestionLink
from apps.courses.validator import VariantValidator
from apps.courses.ai_service import (
    deepseek_verification_available,
    get_deepseek_model,
)
from apps.common.ai.components.base import QuestionInput
from apps.common.ai.components.result_verifier import ResultVerifierComponent
from apps.common.ai.components.variant_generator import VariantGeneratorComponent
from apps.common.ai.exceptions import AIConfigError, AIResponseError
from apps.common.exceptions import AIRequestError
from apps.parser.models import ExamQuestion, QuestionOption

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def convert_course_material(self, material_id: str) -> dict:
    """在后台将 Word 课程资料转为 PDF，不阻塞预览请求。"""
    try:
        material = CourseMaterial.objects.get(id=material_id)
    except CourseMaterial.DoesNotExist:
        logger.warning('Course material conversion skipped: material does not exist: %s', material_id)
        return {'status': 'skipped', 'material_id': material_id, 'reason': 'not_found'}

    if material.is_deleted:
        return {'status': 'skipped', 'material_id': material_id, 'reason': 'deleted'}
    if material.file_type.lower() not in {'doc', 'docx'}:
        return {'status': 'skipped', 'material_id': material_id, 'reason': 'not_word'}

    material.conversion_status = CourseMaterial.ConversionStatus.CONVERTING
    material.conversion_started_at = timezone.now()
    material.conversion_error = ''
    material.save(update_fields=['conversion_status', 'conversion_started_at', 'conversion_error'])

    try:
        source_path = os.path.join(settings.MEDIA_ROOT, material.file_path)
        pdf_path = convert_service.convert_word_to_pdf(source_path)
        if not pdf_path:
            raise RuntimeError('Word conversion to PDF failed')

        material.converted_pdf_path = os.path.relpath(pdf_path, settings.MEDIA_ROOT).replace(os.sep, '/')
        material.conversion_status = CourseMaterial.ConversionStatus.COMPLETED
        material.conversion_completed_at = timezone.now()
        material.conversion_error = ''
        material.save(update_fields=[
            'converted_pdf_path', 'conversion_status', 'conversion_completed_at', 'conversion_error',
        ])
        logger.info('Course material conversion completed: %s', material.id)
        return {'status': 'completed', 'material_id': str(material.id)}
    except Exception as exc:
        material.conversion_status = CourseMaterial.ConversionStatus.FAILED
        material.conversion_completed_at = timezone.now()
        material.conversion_error = str(exc)[:2000]
        material.save(update_fields=['conversion_status', 'conversion_completed_at', 'conversion_error'])
        logger.exception('Course material conversion failed: %s', material.id)
        return {'status': 'failed', 'material_id': str(material.id), 'reason': str(exc)}


def variant_generator_component_factory() -> VariantGeneratorComponent:
    return VariantGeneratorComponent()


def result_verifier_component_factory() -> ResultVerifierComponent:
    return ResultVerifierComponent()


def _close_component(component) -> None:
    close = getattr(component, "close", None)
    if callable(close):
        close()


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


def _build_question_input(question_data: dict) -> QuestionInput:
    return QuestionInput(
        stem=question_data.get('stem', ''),
        options=question_data.get('options'),
        answer=question_data.get('answer', ''),
        solution=question_data.get('solution', ''),
        metadata={
            'question_type': question_data.get('question_type', 'unknown'),
            'analysis': question_data.get('analysis', ''),
            'difficulty': question_data.get('difficulty', 3),
            'knowledge_points': question_data.get('knowledge_points', []),
        },
    )


def _save_variant_as_question(variant_task: VariantTask, variant_data: dict) -> ExamQuestion:
    """将生成的变式题保存为 ExamQuestion 记录，并建立课程关联。"""
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
                           tree_node_id: int = None, mission_id: str = None,
                           level_id: str = None, target_student_id: str = None,
                           variant_task_id: str = None) -> dict:
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

    # 2. Reuse the pre-created database task when called by the API. Direct
    # task invocations and legacy callers still create one here.
    if variant_task_id:
        try:
            variant_task = VariantTask.objects.get(id=variant_task_id, original_question=original)
        except VariantTask.DoesNotExist:
            variant_task = VariantTask.objects.create(
                id=variant_task_id,
                original_question=original,
                variant_mode=variant_mode,
                status='pending',
            )
    else:
        variant_task = VariantTask.objects.create(
            original_question=original,
            variant_mode=variant_mode,
            status='pending',
        )
    variant_task.status = 'running'
    variant_task.save(update_fields=['status'])

    try:
        # 3. 构建原题数据
        question_data = _build_question_data(original)

        # 完整性检查
        if not question_data.get('stem'):
            raise ValueError("原题题干为空，无法生成变式题")

        variant_task.generator_result = {'status': 'data_prepared', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')}
        variant_task.save(update_fields=['generator_result'])

        # 4. 调用 qwen3.7-plus 生成变式题
        logger.info("[VariantTask] Calling shared variant generator")
        generator = variant_generator_component_factory()
        try:
            generation = generator.generate(
                _build_question_input(question_data), variant_mode
            )
        finally:
            _close_component(generator)
        variant_data = generation['parsed']
        raw_response = generation['raw_response']
        qwen_model = generation['model']
        generation_time_ms = generation['latency_ms']

        logger.info(f"[VariantTask] Generation complete in {generation_time_ms}ms")
        variant_task.generator_result = {
            'status': 'generated',
            'model': qwen_model,
            'latency_ms': generation_time_ms,
            'raw_response': raw_response[:2000],
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        }
        variant_task.save(update_fields=['generator_result'])

        # 5. 程序校验（校验失败为硬失败，不消耗 Celery 重试配额）
        validator = VariantValidator()
        validation_issues = validator.validate(variant_data, original)

        if validation_issues:
            logger.warning(f"[VariantTask] Validation issues: {validation_issues}")
            variant_task.generator_result['validation_issues'] = validation_issues
            variant_task.save(update_fields=['generator_result'])
            raise ValueError(f"变式题校验不通过: {', '.join(validation_issues)}")

        # 6. DeepSeek 校验器验证
        logger.info("[VariantTask] Calling shared DeepSeek verifier")
        verifier_start = time.time()
        verifier_available = deepseek_verification_available()
        deepseek_model = get_deepseek_model() if verifier_available else None
        if not verifier_available:
            logger.warning("[VariantTask] DeepSeek API key not configured, skipping AI verification")

        verifier_result = None
        verifier_retry_budget = 1  # DeepSeek 校验器至少有 1 次重试，独立于 Celery 重试
        if verifier_available:
            verifier = result_verifier_component_factory()
            try:
                for _attempt in range(verifier_retry_budget + 1):
                    try:
                        verifier_result = verifier.verify(
                            'variant_verify_deepseek',
                            question_data,
                            variant_data,
                        )
                        verifier_time_ms = int((time.time() - verifier_start) * 1000)
                        verifier_result.setdefault('latency_ms', verifier_time_ms)
                        verifier_result.setdefault('model', deepseek_model)

                        logger.info(f"[VariantTask] Verifier result: passed={verifier_result.get('passed')}, "
                                   f"score={verifier_result.get('score')}")

                        # DeepSeek 校验不通过，重试一次
                        if not verifier_result.get('passed'):
                            logger.warning("[VariantTask] DeepSeek verifier failed, retrying once...")
                            continue

                        break  # 校验通过，退出重试

                    except (AIConfigError, AIRequestError, AIResponseError) as e:
                        logger.warning("[VariantTask] DeepSeek verification failed")
                        verifier_result = {'error': str(e), 'model': deepseek_model}
                        if _attempt < verifier_retry_budget:
                            time.sleep(15)
                            continue
                        break
            finally:
                _close_component(verifier)

        variant_task.verifier_result = verifier_result
        variant_task.generated_question = variant_data
        variant_task.status = 'success'
        variant_task.completed_at = timezone.now()
        variant_task.save(update_fields=['verifier_result', 'generated_question', 'status', 'completed_at'])

        # 7. 保存为 ExamQuestion
        try:
            variant_q = _save_variant_as_question(variant_task, variant_data)
            if mission_id and level_id:
                from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
                mission = LearningMission.objects.get(pk=mission_id)
                level = MissionLevel.objects.get(pk=level_id, mission=mission)
                next_sort = MissionQuestionRel.objects.filter(level=level).count()
                MissionQuestionRel.objects.create(
                    mission=mission, level=level, question_id=variant_q.id,
                    sort_no=next_sort, source_type='variant',
                    target_student_ids=[str(target_student_id)] if target_student_id else [],
                )
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
