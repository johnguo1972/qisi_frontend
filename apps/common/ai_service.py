"""Backward-compatible facade for the shared question AI components."""
import logging
import time
import os
from django.conf import settings
from apps.common.exceptions import AIRequestError
from apps.common.ai.client import AIClient
from apps.common.ai.config import load_ai_config
from apps.common.ai.exceptions import AIConfigError, AIPromptError, AIResponseError
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai.types import AIResult
from apps.common.ai.components import (
    KnowledgeAnalysisComponent,
    ModeAAnswerComponent,
    ModeBAnswerComponent,
    ModeCAnswerComponent,
    QuestionComponentFactory,
    QuestionInput,
    QuestionProbeComponent,
    ResultVerifierComponent,
    VisionExtractionComponent,
)

logger = logging.getLogger(__name__)


class _LegacyComponentClient:
    """Route component calls through legacy mock hooks, never through HTTP."""

    def __init__(self, service: "AIReviewService") -> None:
        self._service = service

    def complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images=(),
        trace_id: str | None = None,
    ) -> AIResult:
        if images:
            content = self._service._call_ai_multimodal(
                system,
                user,
                list(images),
                task_key=task_key,
            )
        else:
            content = self._service._call_ai(
                system,
                user,
                task_key=task_key,
            )
        task = self._service._config.get_task_config(task_key)
        return AIResult(
            content=content,
            provider=task.provider,
            model=task.model,
            latency_ms=0,
            raw_response={},
        )


class AIReviewService:
    """Thin compatibility adapter retaining the legacy public API."""

    def __init__(
        self,
        component_factory=None,
        *,
        ai_client=None,
        prompt_registry=None,
    ):
        self._config = load_ai_config()
        self._ai_client = ai_client or AIClient()
        self._prompt_registry = prompt_registry or PromptRegistry(self._config)
        self.api_key = self._config.get_provider_config("qwen").api_key
        self._component_client = _LegacyComponentClient(self)
        self._component_factory = component_factory or QuestionComponentFactory(
            self._component_client, self._prompt_registry
        )

    def _get_model(
        self, override_model: str = None, *, default_model: str = None
    ) -> str:
        """Return compatibility metadata without changing configured routing."""
        task_key = (
            "question_probe"
            if default_model and "flash" in default_model
            else "knowledge_analysis"
        )
        configured_model = self._config.get_task_config(task_key).model
        configured_models = {
            self._config.get_task_config(key).model
            for key in self._config.task_keys
        }
        if override_model in configured_models:
            return override_model
        return configured_model

    def _call_ai(self, system_prompt: str, user_prompt: str,
                 model: str = None, max_tokens: int = 4000,
                 default_model: str = None, *, task_key: str | None = None) -> str:
        """Legacy mock hook delegating to the single configured ``AIClient``."""
        if not task_key:
            raise AIRequestError("Configured AI task key is required")
        return self._ai_client.complete(
            task_key, system=system_prompt, user=user_prompt
        ).content

    def _call_ai_multimodal(self, system_prompt: str, user_text: str,
                            image_urls: list, model: str = None,
                            max_tokens: int = 8000,
                            default_model: str = None, *,
                            task_key: str | None = None) -> str:
        """Legacy multimodal mock hook delegating to configured ``AIClient``."""
        if not task_key:
            raise AIRequestError("Configured AI task key is required")
        return self._ai_client.complete(
            task_key,
            system=system_prompt,
            user=user_text,
            images=tuple(image_urls),
        ).content

    def _get_question_image_urls(self, question, max_images: int = 5) -> list:
        """Get OSS URLs for all question images.

        Uploads images to OSS if not already uploaded.
        Limits to max_images to control token usage.

        Args:
            question: ExamQuestion instance
            max_images: Maximum number of images to include (default: 5)

        Returns:
            List of image URLs (OSS URLs if available, None if upload fails)
        """
        from apps.parser.models import QuestionImage

        images = list(QuestionImage.objects.filter(
            question=question
        ).order_by('sort_order')[:max_images])

        urls = []
        for img in images:
            if img.file_path:
                local_path = str(settings.MEDIA_ROOT / img.file_path)
                if os.path.exists(local_path):
                    oss_url = self._upload_to_oss(local_path, img.file_path)
                    if oss_url:
                        urls.append(oss_url)
                    else:
                        logger.warning(f'Could not get OSS URL for {img.file_path}, skipping')

        return urls

    def _upload_to_oss(self, local_path: str, oss_key: str) -> str | None:
        """Delegate uploads to the existing OSS service."""
        from pathlib import PurePosixPath
        from apps.common.oss_service import upload_crop_image_safe

        parent = str(PurePosixPath(oss_key).parent)
        prefix = parent if parent != "." else "question_crops"
        return upload_crop_image_safe(local_path, prefix=prefix)

    def _component(self, component_type):
        return self._component_factory(component_type)

    @staticmethod
    def _run_component(component, question_input: QuestionInput) -> dict:
        try:
            result = component.run(question_input)
        except (AIConfigError, AIPromptError, AIResponseError) as error:
            raise AIRequestError(str(error)) from None
        if not isinstance(result, dict):
            raise AIRequestError(
                "AI question component returned a non-object response"
            )
        return result

    @staticmethod
    def _question_input(question, image_urls=(), **metadata) -> QuestionInput:
        return QuestionInput(
            stem=getattr(question, "stem", "") or "",
            options=getattr(question, "options", None),
            answer=getattr(question, "answer", "") or "",
            solution=getattr(question, "solution", "") or "",
            image_urls=tuple(image_urls),
            metadata={
                "analysis": getattr(question, "analysis", "") or "",
                **metadata,
            },
        )

    def analyze_knowledge(self, question, model: str = None) -> dict:
        """Analyze knowledge points through the configured shared component."""
        question_input = self._question_input(
            question, subject_hint=getattr(question, "subject", "") or ""
        )
        return self._run_component(
            self._component(KnowledgeAnalysisComponent), question_input
        )

    def generate_answer_a(self, question, knowledge_data: dict = None,
                          model: str = None) -> dict:
        """Generate the legacy Mode A shape through ``ModeAAnswerComponent``."""
        return self._generate_mode(
            ModeAAnswerComponent, question, knowledge_data
        )

    def generate_answer_b(self, question, knowledge_data: dict = None,
                          model: str = None) -> dict:
        """Generate the legacy Mode B shape through ``ModeBAnswerComponent``."""
        return self._generate_mode(
            ModeBAnswerComponent, question, knowledge_data
        )

    def generate_answer_c(self, question, knowledge_data: dict = None,
                          model: str = None) -> dict:
        """Generate the legacy Mode C shape through ``ModeCAnswerComponent``."""
        return self._generate_mode(
            ModeCAnswerComponent, question, knowledge_data
        )

    def _generate_mode(self, component_type, question, knowledge_data) -> dict:
        image_urls = self._get_question_image_urls(question)
        knowledge_refs = []
        if isinstance(knowledge_data, dict):
            knowledge_refs = knowledge_data.get("knowledge_points") or []
        question_input = self._question_input(
            question,
            image_urls,
            knowledge_refs=knowledge_refs,
            vision_result={},
        )
        return self._run_component(
            self._component(component_type), question_input
        )

    def process_question_full(self, question_id: int, model: str = None) -> dict:
        """Full pipeline: knowledge analysis + A/B/C answer generation.

        Returns: {
            'knowledge': {...},
            'answer_a': {...},
            'answer_b': {...},
            'answer_c': {...},
            'errors': {'knowledge': '...', 'answer_a': '...', ...}
        }
        """
        from apps.parser.models import ExamQuestion

        question = ExamQuestion.objects.get(id=question_id)
        errors = {}
        results = {}

        # Step 1: Knowledge analysis
        try:
            knowledge_data = self.analyze_knowledge(question, model=model)
            if not isinstance(knowledge_data, dict):
                raise AIRequestError(f"AI returned non-dict response for knowledge analysis: {type(knowledge_data).__name__}")
            knowledge_data['model'] = self._get_model(model)
            knowledge_data['generated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            knowledge_data['confirmed'] = False
            knowledge_data['confirmed_at'] = None
            knowledge_data['error'] = None
            results['knowledge'] = knowledge_data
        except AIRequestError as e:
            errors['knowledge'] = str(e)
            results['knowledge'] = {
                'error': str(e), 'model': self._get_model(model),
                'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }

        knowledge_ref = results.get('knowledge')

        # Step 2: A mode
        try:
            answer_a = self.generate_answer_a(question, knowledge_ref, model=model)
            if not isinstance(answer_a, dict):
                raise AIRequestError(f"AI returned non-dict response for answer_a: {type(answer_a).__name__}")
            answer_a['mode'] = 'A'
            answer_a['model'] = self._get_model(model)
            answer_a['generated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            answer_a['confirmed'] = False
            answer_a['confirmed_at'] = None
            answer_a['edited_content'] = None
            answer_a['error'] = None
            results['answer_a'] = answer_a
        except AIRequestError as e:
            errors['answer_a'] = str(e)
            results['answer_a'] = {
                'error': str(e), 'model': self._get_model(model),
                'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }

        # Step 3: B mode
        try:
            answer_b = self.generate_answer_b(question, knowledge_ref, model=model)
            if not isinstance(answer_b, dict):
                raise AIRequestError(f"AI returned non-dict response for answer_b: {type(answer_b).__name__}")
            answer_b['mode'] = 'B'
            answer_b['model'] = self._get_model(model)
            answer_b['generated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            answer_b['confirmed'] = False
            answer_b['confirmed_at'] = None
            answer_b['edited_content'] = None
            answer_b['error'] = None
            results['answer_b'] = answer_b
        except AIRequestError as e:
            errors['answer_b'] = str(e)
            results['answer_b'] = {
                'error': str(e), 'model': self._get_model(model),
                'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }

        # Step 4: C mode
        try:
            answer_c = self.generate_answer_c(question, knowledge_ref, model=model)
            if not isinstance(answer_c, dict):
                raise AIRequestError(f"AI returned non-dict response for answer_c: {type(answer_c).__name__}")
            answer_c['mode'] = 'C'
            answer_c['model'] = self._get_model(model)
            answer_c['generated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            answer_c['confirmed'] = False
            answer_c['confirmed_at'] = None
            answer_c['edited_content'] = None
            answer_c['error'] = None
            results['answer_c'] = answer_c
        except AIRequestError as e:
            errors['answer_c'] = str(e)
            results['answer_c'] = {
                'error': str(e), 'model': self._get_model(model),
                'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            }

        results['errors'] = errors
        return results

    def probe_and_norm(self, question, image_urls: list, model: str = None) -> dict:
        """Step 1: Probe & Norm — 轻量探查 + 规范化."""
        question_input = self._question_input(question, image_urls)
        return self._run_component(
            self._component(QuestionProbeComponent), question_input
        )

    def vision_extraction(self, question, image_urls: list,
                          normalized_text: str, model: str = None) -> dict:
        """Step 2: Vision Extraction — 统一读图."""
        question_input = self._question_input(
            question, image_urls, normalized_text=normalized_text
        )
        return self._run_component(
            self._component(VisionExtractionComponent), question_input
        )

    def solve_mode_a(self, question, image_urls: list, normalized_text: str,
                     vision_result: dict, knowledge_refs: str,
                     model: str = None) -> dict:
        """Step 3a: A 模式求解."""
        return self._solve_mode(
            ModeAAnswerComponent, question, image_urls, normalized_text,
            vision_result, knowledge_refs
        )

    def solve_mode_b(self, question, image_urls: list, normalized_text: str,
                     vision_result: dict, knowledge_refs: str,
                     model: str = None) -> dict:
        """Step 3b: B 模式求解."""
        return self._solve_mode(
            ModeBAnswerComponent, question, image_urls, normalized_text,
            vision_result, knowledge_refs
        )

    def solve_mode_c(self, question, image_urls: list, normalized_text: str,
                     vision_result: dict, knowledge_refs: str,
                     model: str = None) -> dict:
        """Step 3c: C 模式求解."""
        return self._solve_mode(
            ModeCAnswerComponent, question, image_urls, normalized_text,
            vision_result, knowledge_refs
        )

    def _solve_mode(
        self, component_type, question, image_urls, normalized_text,
        vision_result, knowledge_refs
    ) -> dict:
        question_input = self._question_input(
            question,
            image_urls,
            normalized_text=normalized_text,
            vision_result=vision_result,
            knowledge_refs=knowledge_refs,
        )
        return self._run_component(
            self._component(component_type), question_input
        )

    def verify_result(self, normalized_text: str, vision_result: dict,
                      solver_output: dict, model: str = None) -> dict:
        """Step 4: 解后校验."""
        question_input = QuestionInput(
            stem=normalized_text,
            metadata={
                "normalized_text": normalized_text,
                "vision_result": vision_result,
                "solver_output": solver_output,
            },
        )
        return self._run_component(
            self._component(ResultVerifierComponent), question_input
        )

    def analyze_knowledge_points(self, question, normalized_text: str, subject_hint: str = '',
                                 model: str = None) -> dict:
        """知识点识别：输出 1-5 个知识点 module + 难度（供 save 阶段匹配 knowledge_points 表）."""
        question_input = self._question_input(
            question,
            normalized_text=normalized_text,
            subject_hint=subject_hint,
        )
        return self._run_component(
            self._component(KnowledgeAnalysisComponent), question_input
        )

    def process_question_full_v2(self, question_id: int, model: str = None) -> dict:
        """Full 6-step pipeline: Probe -> Vision -> Solver A/B/C -> Verifier."""
        from django.utils import timezone
        from apps.parser.models import ExamQuestion

        question = ExamQuestion.objects.get(id=question_id)
        errors = {}
        results = {}

        # Update status to running
        question.ai_processing_status = 'running'
        question.save(update_fields=['ai_processing_status'])

        # Get image URLs
        image_urls = self._get_question_image_urls(question)
        logger.info(f'[AI] Got {len(image_urls)} image URLs for question {question_id}')

        # Step 1: Probe & Norm
        try:
            probe_result = self.probe_and_norm(question, image_urls, model=model)
            normalized_text = probe_result.get('normalized_text', question.stem or '')
            results['probe'] = probe_result
        except AIRequestError as e:
            errors['probe'] = str(e)
            results['probe'] = {'error': str(e)}
            normalized_text = question.stem or ''

        # Step 1.5: Knowledge analysis（识别 1-5 个知识点 + 难度，供 save 匹配并更新）
        try:
            knowledge = self.analyze_knowledge_points(
                question, normalized_text,
                subject_hint=results.get('probe', {}).get('subject', ''),
                model=model,
            )
            results['knowledge'] = knowledge
        except AIRequestError as e:
            errors['knowledge'] = str(e)
            results['knowledge'] = {'error': str(e)}

        # Step 2: Vision Extraction
        try:
            vision_result = self.vision_extraction(
                question, image_urls, normalized_text, model=model
            )
            results['vision'] = vision_result
        except AIRequestError as e:
            errors['vision'] = str(e)
            results['vision'] = {'error': str(e)}
            vision_result = {}

        # Build knowledge refs
        knowledge_refs = ""
        if results.get('probe', {}).get('topic_tags_top3'):
            knowledge_refs = ", ".join(results['probe']['topic_tags_top3'])

        # Step 3a: Solver A
        try:
            answer_a = self.solve_mode_a(
                question, image_urls, normalized_text, vision_result,
                knowledge_refs, model=model
            )
            results['answer_a'] = answer_a
        except AIRequestError as e:
            errors['answer_a'] = str(e)
            results['answer_a'] = {'error': str(e)}

        # Step 3b: Solver B
        try:
            answer_b = self.solve_mode_b(
                question, image_urls, normalized_text, vision_result,
                knowledge_refs, model=model
            )
            results['answer_b'] = answer_b
        except AIRequestError as e:
            errors['answer_b'] = str(e)
            results['answer_b'] = {'error': str(e)}

        # Step 3c: Solver C
        try:
            answer_c = self.solve_mode_c(
                question, image_urls, normalized_text, vision_result,
                knowledge_refs, model=model
            )
            results['answer_c'] = answer_c
        except AIRequestError as e:
            errors['answer_c'] = str(e)
            results['answer_c'] = {'error': str(e)}

        # Step 4: Verifier
        try:
            verifier = self.verify_result(
                normalized_text, vision_result,
                results.get('answer_a', {}), model=model
            )
            results['verifier'] = verifier
        except AIRequestError as e:
            errors['verifier'] = str(e)
            results['verifier'] = {'error': str(e)}

        results['errors'] = errors
        results['image_count'] = len(image_urls)

        # Update status
        if errors:
            question.ai_processing_status = 'failed'
        else:
            question.ai_processing_status = 'success'
        question.ai_processed_at = timezone.now()
        question.save(update_fields=['ai_processing_status', 'ai_processed_at'])

        return results

    def save_results_to_question(self, question_id: int, results: dict):
        """Save AI processing results to ExamQuestion record.

        Also matches knowledge point IDs against the knowledge_points table.
        """
        from apps.parser.models import ExamQuestion
        from apps.knowledge.models import KnowledgePoint

        question = ExamQuestion.objects.get(id=question_id)

        # Determine subject from the question record
        subject_map = {'math': 'math', 'physics': 'physics', '数学': 'math', '物理': 'physics'}
        question_subject = subject_map.get(question.subject, 'math')

        # Enrich knowledge points with actual DB records
        # Validate and correct: AI may return a wrong id that doesn't match the module name
        if 'knowledge' in results and results['knowledge'].get('error') is None:
            kp_data = results['knowledge']
            matched_kps = []
            if kp_data.get('knowledge_points'):
                for kp in kp_data['knowledge_points']:
                    ai_module = (kp.get('module') or '').strip()
                    kp_subject = (kp.get('subject') or question_subject).strip()
                    if not ai_module:
                        continue
                    # 匹配 knowledge_points 表的 module 字段：精确 -> 模糊 contains（同 subject 优先，再跨 subject）
                    db_kp = KnowledgePoint.objects.filter(subject=kp_subject, module=ai_module).first()
                    if not db_kp:
                        db_kp = KnowledgePoint.objects.filter(subject=kp_subject, module__icontains=ai_module).first()
                    if not db_kp:
                        db_kp = KnowledgePoint.objects.filter(module__icontains=ai_module).first()
                    if db_kp:
                        kp['id'] = db_kp.id
                        kp['module'] = db_kp.module
                        kp['full_label'] = db_kp.full_label
                        matched_kps.append({'id': db_kp.id, 'module': db_kp.module})
                        logger.info(f'[AI] matched knowledge point: ai="{ai_module}" -> id={db_kp.id} module="{db_kp.module}"')
                    else:
                        kp['id'] = None
                        kp['full_label'] = ai_module
                        logger.info(f'[AI] no DB match for knowledge point: "{ai_module}"')
            question.ai_knowledge_enrichment = kp_data
            # 用匹配到 DB 的知识点更新题目的 knowledge_points 关联
            if matched_kps:
                question.knowledge_points = matched_kps
            # 难度更新
            diff = kp_data.get('difficulty')
            if diff and isinstance(diff, str) and len(diff) == 2 and diff[0] == 'L' and diff[1].isdigit():
                level = int(diff[1])
                if 1 <= level <= 5:
                    question.difficulty = level

        # Save probe result
        if 'probe' in results:
            question.ai_probe_result = results['probe']

        # Save vision extract
        if 'vision' in results:
            question.ai_vision_extract = results['vision']

        # Save verifier result
        if 'verifier' in results:
            question.ai_verifier_result = results['verifier']

        # Save A/B/C answers (existing logic)
        if 'answer_a' in results and not results['answer_a'].get('error'):
            question.ai_answer_a = results['answer_a']
        if 'answer_b' in results and not results['answer_b'].get('error'):
            question.ai_answer_b = results['answer_b']
        if 'answer_c' in results and not results['answer_c'].get('error'):
            question.ai_answer_c = results['answer_c']

        question.save()

        # Log what was actually saved to DB
        logger.info(f'[AI SAVE] question_id={question_id} DB state:')
        if question.ai_answer_a:
            for k2 in ('steps', 'answer', 'content', 'options', 'dialogue'):
                if k2 in question.ai_answer_a:
                    v = question.ai_answer_a[k2]
                    logger.info(f'[AI SAVE] ai_answer_a.{k2} (len={len(str(v))}): {str(v)[:500]}')
        if question.ai_answer_b:
            for k2 in ('steps', 'answer', 'content', 'options', 'dialogue'):
                if k2 in question.ai_answer_b:
                    v = question.ai_answer_b[k2]
                    logger.info(f'[AI SAVE] ai_answer_b.{k2} (len={len(str(v))}): {str(v)[:500]}')
        if question.ai_answer_c:
            for k2 in ('steps', 'answer', 'content', 'options', 'dialogue'):
                if k2 in question.ai_answer_c:
                    v = question.ai_answer_c[k2]
                    logger.info(f'[AI SAVE] ai_answer_c.{k2} (len={len(str(v))}): {str(v)[:500]}')
