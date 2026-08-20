"""Backward-compatible facade for the shared question AI components."""
from copy import deepcopy
import logging
import time
import os
import threading
from django.conf import settings
from pydantic import BaseModel, ValidationError
from apps.common.exceptions import AIRequestError
from apps.common.ai.client import AIClient
from apps.common.ai.config import load_ai_config
from apps.common.ai.exceptions import AIConfigError, AIPromptError, AIResponseError
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai.types import AIResult
from apps.common.ai.components import (
    DeepSeekFinalReviewComponent,
    DeepSeekBaselineSolveComponent,
    DeepSeekIndependentVerifierComponent,
    KnowledgeAnalysisComponent,
    ModeAAnswerComponent,
    ModeBAnswerComponent,
    ModeBStructureRepairComponent,
    ModeCAnswerComponent,
    QuestionComponentFactory,
    QuestionInput,
    QuestionProbeComponent,
    ResultVerifierComponent,
    VisionExtractionComponent,
)
from apps.common.ai.answer_arbitration import (
    ArbitrationError,
    ArbitrationOutcome,
    ArbitrationProviderError,
    ModeAnswerArbitrator,
)
from apps.common.ai.question_context import QuestionContextBuilder, question_context_hash
from apps.common.ai.schemas import ModeAResponse, ModeBResponse, ModeCResponse

logger = logging.getLogger(__name__)


_MODE_RESPONSE_SCHEMAS = {
    "A": ModeAResponse,
    "B": ModeBResponse,
    "C": ModeCResponse,
}
_SHARED_VERIFIER_FIELDS = (
    "context_hash",
    "independent_answer",
    "reference_answer_valid",
    "reference_analysis_valid",
    "reference_issues",
    "key_facts",
    "confidence",
)
_MODE_ARBITRATION_ATTEMPTS = 2
_PIPELINE_CACHE_KEY = "_ai_cache"
_PIPELINE_CACHE_VERSION = 1
_RESPONSE_CONTRACT_FAILURE_MARKERS = (
    "schema",
    "json",
    "validation",
    "corrupted latex",
)


def _is_response_contract_failure(error: BaseException) -> bool:
    """Return whether a failed component result is eligible for B JSON repair.

    Mode B structure repair regenerates a teaching payload.  It cannot repair
    transport, rate-limit, or provider-capacity failures, and routing those
    failures through the repair prompt both wastes a request and obscures the
    true failed provider boundary.
    """
    message = str(error).lower()
    return any(marker in message for marker in _RESPONSE_CONTRACT_FAILURE_MARKERS)


def _safe_arbitration_failure(error: BaseException) -> str:
    """Serialize a stable arbitration boundary without retaining raw provider text."""
    if isinstance(error, ArbitrationProviderError):
        stage = getattr(error, "stage", "")
        if isinstance(stage, str) and stage and stage != "unknown":
            return stage
    return str(error)


def _project_schema_value(value):
    """Project validated mode output to declared public schema fields only."""
    if isinstance(value, BaseModel):
        projected = {}
        for field_name, field in type(value).model_fields.items():
            output_name = field.serialization_alias or field.alias or field_name
            projected[output_name] = _project_schema_value(
                getattr(value, field_name)
            )
        return projected
    if isinstance(value, dict):
        return {
            str(key): _project_schema_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_project_schema_value(item) for item in value]
    return value


def _safe_shared_verifier_result(value) -> dict | None:
    """Return only the reusable DeepSeek audit fields, never mode content."""
    if not isinstance(value, dict):
        return None
    if not all(field in value for field in _SHARED_VERIFIER_FIELDS):
        return None
    if not all(
        isinstance(value[field], str) and bool(value[field].strip())
        for field in ("context_hash", "independent_answer")
    ):
        return None
    for field in ("reference_answer_valid", "reference_analysis_valid"):
        flag = value[field]
        if flag is not None and not isinstance(flag, bool):
            return None
    issues = value["reference_issues"]
    facts = value["key_facts"]
    confidence = value["confidence"]
    if (
        not isinstance(issues, (list, tuple))
        or not all(isinstance(item, str) for item in issues)
        or not isinstance(facts, (list, tuple))
        or not facts
        or not all(isinstance(item, str) and bool(item.strip()) for item in facts)
        or isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        return None
    return {
        field: deepcopy(value[field])
        for field in _SHARED_VERIFIER_FIELDS
    }


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
        return self._complete(
            task_key,
            system=system,
            user=user,
            images=images,
            trace_id=trace_id,
            single_attempt=False,
        )

    def complete_once(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images=(),
        trace_id: str | None = None,
    ) -> AIResult:
        return self._complete(
            task_key,
            system=system,
            user=user,
            images=images,
            trace_id=trace_id,
            single_attempt=True,
        )

    def _complete(
        self,
        task_key: str,
        *,
        system: str,
        user: str,
        images=(),
        trace_id: str | None = None,
        single_attempt: bool,
    ) -> AIResult:
        if images:
            kwargs = {"task_key": task_key}
            if single_attempt:
                kwargs["single_attempt"] = True
            content = self._service._call_ai_multimodal(
                system,
                user,
                list(images),
                **kwargs,
            )
        else:
            kwargs = {"task_key": task_key}
            if single_attempt:
                kwargs["single_attempt"] = True
            content = self._service._call_ai(system, user, **kwargs)
        provider, model = self._service._task_route(task_key)
        return AIResult(
            content=content,
            provider=provider,
            model=model,
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
        config = load_ai_config()
        self._task_routes = {
            key: (
                config.get_task_config(key).provider,
                config.get_task_config(key).model,
            )
            for key in config.task_keys
        }
        self._ai_client = ai_client
        self._ai_client_lock = threading.Lock()
        self._owns_ai_client = False
        self._prompt_registry = (
            prompt_registry
            if prompt_registry is not None
            else PromptRegistry(config)
        )
        config = None
        self._component_client = None
        self._owns_component_factory = component_factory is None
        if component_factory is None:
            self._component_client = _LegacyComponentClient(self)
            self._component_factory = QuestionComponentFactory(
                self._component_client, self._prompt_registry
            )
        else:
            self._component_factory = component_factory

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()

    def _get_model(
        self, override_model: str = None, *, default_model: str = None
    ) -> str:
        """Return compatibility metadata without changing configured routing."""
        task_key = (
            "question_probe"
            if default_model and "flash" in default_model
            else "knowledge_analysis"
        )
        configured_model = self._task_route(task_key)[1]
        configured_models = {
            model for _provider, model in self._task_routes.values()
        }
        if override_model in configured_models:
            return override_model
        return configured_model

    def _task_route(self, task_key: str) -> tuple[str, str]:
        try:
            return self._task_routes[task_key]
        except KeyError:
            raise AIConfigError("Unknown AI task") from None

    def _call_ai(self, system_prompt: str, user_prompt: str,
                 model: str = None, max_tokens: int = 4000,
                 default_model: str = None, *, task_key: str | None = None,
                 single_attempt: bool = False) -> str:
        """Legacy mock hook delegating to the single configured ``AIClient``."""
        if not task_key:
            raise AIRequestError("Configured AI task key is required")
        client = self._provider_client()
        complete = (
            getattr(client, "complete_once", None)
            if single_attempt
            else client.complete
        )
        if not callable(complete):
            complete = client.complete
        return complete(
            task_key, system=system_prompt, user=user_prompt
        ).content

    def _call_ai_multimodal(self, system_prompt: str, user_text: str,
                            image_urls: list, model: str = None,
                            max_tokens: int = 8000,
                            default_model: str = None, *,
                            task_key: str | None = None,
                            single_attempt: bool = False) -> str:
        """Legacy multimodal mock hook delegating to configured ``AIClient``."""
        if not task_key:
            raise AIRequestError("Configured AI task key is required")
        client = self._provider_client()
        complete = (
            getattr(client, "complete_once", None)
            if single_attempt
            else client.complete
        )
        if not callable(complete):
            complete = client.complete
        return complete(
            task_key,
            system=system_prompt,
            user=user_text,
            images=tuple(image_urls),
        ).content

    def _provider_client(self):
        client = self._ai_client
        if client is None:
            with self._ai_client_lock:
                if self._ai_client is None:
                    self._ai_client = AIClient()
                    self._owns_ai_client = True
                client = self._ai_client
        return client

    def close(self) -> None:
        """Close only the lazily-created client owned by this service."""
        if self._owns_component_factory:
            factory_close = getattr(self._component_factory, "close", None)
            if callable(factory_close):
                factory_close()
        with self._ai_client_lock:
            if self._ai_client is None or not self._owns_ai_client:
                return
            client = self._ai_client
            self._ai_client = None
            self._owns_ai_client = False
        client.close()

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

    def _processing_input_hash(self, question, image_urls, model: str | None) -> str:
        """Return the cache identity for AI preprocessing inputs only."""
        context = QuestionContextBuilder.build(
            question,
            image_urls=image_urls,
            normalized_text="",
            vision_result={},
            knowledge_refs="",
        )
        # An explicit caller model is part of the request contract.  A model
        # override must therefore never receive preprocessing from another
        # model route.
        return f"{question_context_hash(context)}:{model or ''}"

    @staticmethod
    def _cached_pipeline_result(value, input_hash: str) -> dict | None:
        if not isinstance(value, dict) or value.get("error"):
            return None
        metadata = value.get(_PIPELINE_CACHE_KEY)
        if not isinstance(metadata, dict):
            return None
        if (
            metadata.get("version") != _PIPELINE_CACHE_VERSION
            or metadata.get("input_hash") != input_hash
        ):
            return None
        return deepcopy(value)

    @staticmethod
    def _with_pipeline_cache(result: dict, input_hash: str) -> dict:
        cached = deepcopy(result)
        cached[_PIPELINE_CACHE_KEY] = {
            "version": _PIPELINE_CACHE_VERSION,
            "input_hash": input_hash,
        }
        return cached

    @staticmethod
    def _without_pipeline_cache_metadata(value):
        if not isinstance(value, dict):
            return value
        cleaned = deepcopy(value)
        cleaned.pop(_PIPELINE_CACHE_KEY, None)
        return cleaned

    @staticmethod
    def _cached_shared_verification(
        question,
        *,
        image_urls,
        normalized_text: str,
        vision_result: dict,
        knowledge_refs: str,
    ) -> dict | None:
        shared = _safe_shared_verifier_result(
            getattr(question, "ai_verifier_result", None)
        )
        if shared is None:
            return None
        clean_vision = AIReviewService._without_pipeline_cache_metadata(vision_result)
        context = QuestionContextBuilder.build(
            question,
            image_urls=image_urls,
            normalized_text=normalized_text,
            vision_result=clean_vision,
            knowledge_refs=knowledge_refs,
        )
        return shared if shared["context_hash"] == question_context_hash(context) else None

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
        image_urls = self._get_question_image_urls(question)
        normalized_text = getattr(question, "stem", "") or ""
        knowledge_refs = (
            knowledge_ref.get("knowledge_points", [])
            if isinstance(knowledge_ref, dict)
            else []
        )
        shared_verification = None

        for mode in "ABC":
            answer_key = f"answer_{mode.lower()}"
            try:
                outcome = self.solve_mode_with_arbitration(
                    question,
                    mode=mode,
                    image_urls=image_urls,
                    normalized_text=normalized_text,
                    vision_result={},
                    knowledge_refs=knowledge_refs,
                    cached_verification=shared_verification,
                    model=model,
                )
                answer = dict(outcome.answer)
                answer['mode'] = mode
                route_provider, route_model = self._task_route(
                    f"mode_{mode.lower()}_answer"
                )
                answer['provider'] = route_provider
                answer['model'] = route_model
                answer['generated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
                answer['confirmed'] = False
                answer['confirmed_at'] = None
                answer['edited_content'] = None
                answer['error'] = None
                results[answer_key] = answer
                if outcome.shared_verifier_result is not None:
                    shared_verification = _safe_shared_verifier_result(
                        outcome.shared_verifier_result
                    )
            except (AIRequestError, ArbitrationError) as error:
                failure = _safe_arbitration_failure(error)
                errors[answer_key] = failure
                results[answer_key] = {
                    'error': failure,
                    'provider': self._task_route(
                        f"mode_{mode.lower()}_answer"
                    )[0],
                    'model': self._task_route(
                        f"mode_{mode.lower()}_answer"
                    )[1],
                    'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                }

        if shared_verification is not None and not errors:
            results['verifier'] = deepcopy(shared_verification)
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

    def solve_unanswered_question_baseline(
        self,
        question,
        *,
        image_urls=(),
        normalized_text="",
        vision_result=None,
        knowledge_refs="",
    ) -> dict:
        """Create the canonical answer/analysis baseline for a question without one."""
        context = QuestionContextBuilder.build(
            question,
            image_urls=image_urls,
            normalized_text=normalized_text,
            vision_result=vision_result,
            knowledge_refs=knowledge_refs,
        )
        component = self._component(DeepSeekBaselineSolveComponent)
        for _attempt in range(2):
            result = self._run_component(component, context)
            if result["confidence"] >= 0.80:
                return {
                    **result,
                    "context_hash": question_context_hash(context),
                }
        raise AIRequestError("baseline_invalid")

    def solve_mode_with_arbitration(
        self,
        question,
        *,
        mode,
        image_urls=(),
        normalized_text="",
        vision_result=None,
        knowledge_refs="",
        cached_verification=None,
        model=None,
    ) -> ArbitrationOutcome:
        """Generate and verify one mode against one complete question context.

        ``model`` remains a compatibility argument: the configured task route
        continues to select the provider model, while callers may retain the
        existing supported override as result metadata.  DeepSeek stages always
        use their own fixed task keys.
        """
        normalized_mode = mode.strip().upper() if isinstance(mode, str) else ""
        component_types = {
            "A": ModeAAnswerComponent,
            "B": ModeBAnswerComponent,
            "C": ModeCAnswerComponent,
        }
        component_type = component_types.get(normalized_mode)
        if component_type is None:
            raise ArbitrationProviderError()

        # Preserve the legacy supported/unsupported override behavior without
        # allowing a Qwen choice to leak into either fixed DeepSeek route.
        self._get_model(model)
        context = QuestionContextBuilder.build(
            question,
            image_urls=image_urls,
            normalized_text=normalized_text,
            vision_result=vision_result,
            knowledge_refs=knowledge_refs,
            target_mode=normalized_mode,
        )
        generator = self._component(component_type)

        def generate(_mode, question_input):
            try:
                return self._run_component(generator, question_input)
            except AIRequestError as error:
                if (
                    normalized_mode != "B"
                    or not _is_response_contract_failure(error)
                ):
                    raise
                logger.warning(
                    "Mode B schema response rejected; regenerating once",
                    extra={"mode": "B", "stage": "qwen_structure_repair"},
                )
                try:
                    return self._run_component(
                        self._component(ModeBStructureRepairComponent), question_input
                    )
                except AIRequestError as repair_error:
                    raise ArbitrationProviderError(
                        "qwen_structure_repair"
                    ) from repair_error

        def independent_verify(_mode, question_input):
            return self._run_component(
                self._component(DeepSeekIndependentVerifierComponent),
                question_input,
            )

        def final_review(
            _mode, question_input, qwen_result, independent_result, conflicts
        ):
            review_input = QuestionInput(
                stem=question_input.stem,
                options=question_input.options,
                answer=question_input.answer,
                solution=question_input.solution,
                image_urls=question_input.image_urls,
                metadata={
                    **dict(question_input.metadata),
                    "target_mode": normalized_mode,
                    "qwen_result": qwen_result,
                    "independent_result": independent_result,
                    "conflicts": list(conflicts),
                },
            )
            return self._run_component(
                self._component(DeepSeekFinalReviewComponent), review_input
            )

        arbitrator = ModeAnswerArbitrator(
            generate=generate,
            independent_verify=independent_verify,
            final_review=final_review,
        )
        for attempt in range(_MODE_ARBITRATION_ATTEMPTS):
            try:
                outcome = arbitrator.process(
                    normalized_mode,
                    context,
                    cached_verification=cached_verification,
                )
                try:
                    validated_answer = _MODE_RESPONSE_SCHEMAS[
                        normalized_mode
                    ].model_validate(outcome.answer)
                except ValidationError:
                    raise ArbitrationProviderError() from None
                public_answer = _project_schema_value(validated_answer)
                verification = deepcopy(outcome.verification)
                public_answer["verification"] = verification
                return ArbitrationOutcome(
                    answer=public_answer,
                    verification=verification,
                    shared_verifier_result=deepcopy(
                        outcome.shared_verifier_result
                    ),
                )
            except ArbitrationProviderError:
                if attempt + 1 >= _MODE_ARBITRATION_ATTEMPTS:
                    raise
                logger.warning(
                    "AI mode arbitration provider failure; retrying once",
                    extra={"mode": normalized_mode, "attempt": attempt + 1},
                )

        raise RuntimeError("AI mode arbitration retry loop exhausted")

    def solve_unanswered_mode_with_arbitration(
        self,
        question,
        *,
        mode,
        baseline,
        image_urls=(),
        normalized_text="",
        vision_result=None,
        knowledge_refs="",
        model=None,
    ) -> ArbitrationOutcome:
        """Generate one teaching mode for a question trusted by the baseline solve."""
        normalized_mode = mode.strip().upper() if isinstance(mode, str) else ""
        component_type = {
            "A": ModeAAnswerComponent,
            "B": ModeBAnswerComponent,
            "C": ModeCAnswerComponent,
        }.get(normalized_mode)
        if component_type is None:
            raise ArbitrationProviderError()
        self._get_model(model)
        context = QuestionContextBuilder.build(
            question,
            image_urls=image_urls,
            normalized_text=normalized_text,
            vision_result=vision_result,
            knowledge_refs=knowledge_refs,
            target_mode=normalized_mode,
        )
        generator = self._component(component_type)

        def generate(_mode, question_input):
            try:
                return self._run_component(generator, question_input)
            except AIRequestError as error:
                if (
                    normalized_mode != "B"
                    or not _is_response_contract_failure(error)
                ):
                    raise
                logger.warning(
                    "Mode B schema response rejected; regenerating once",
                    extra={"mode": "B", "stage": "qwen_structure_repair"},
                )
                try:
                    return self._run_component(
                        self._component(ModeBStructureRepairComponent), question_input
                    )
                except AIRequestError as repair_error:
                    raise ArbitrationProviderError(
                        "qwen_structure_repair"
                    ) from repair_error

        def independent_verify(_mode, _question_input):
            raise AssertionError("unanswered arbitration never calls independent verifier")

        def final_review(_mode, question_input, qwen_result, baseline_result, conflicts):
            review_input = QuestionInput(
                stem=question_input.stem,
                options=question_input.options,
                answer=question_input.answer,
                solution=question_input.solution,
                image_urls=question_input.image_urls,
                metadata={
                    **dict(question_input.metadata),
                    "target_mode": normalized_mode,
                    "qwen_result": qwen_result,
                    "independent_result": baseline_result,
                    "conflicts": list(conflicts),
                },
            )
            return self._run_component(
                self._component(DeepSeekFinalReviewComponent), review_input
            )

        outcome = ModeAnswerArbitrator(
            generate=generate,
            independent_verify=independent_verify,
            final_review=final_review,
        ).process_unanswered(normalized_mode, context, baseline=baseline)
        try:
            validated_answer = _MODE_RESPONSE_SCHEMAS[normalized_mode].model_validate(
                outcome.answer
            )
        except ValidationError:
            raise ArbitrationProviderError() from None
        public_answer = _project_schema_value(validated_answer)
        verification = deepcopy(outcome.verification)
        public_answer["verification"] = verification
        return ArbitrationOutcome(
            answer=public_answer,
            verification=verification,
            shared_verifier_result=None,
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

    def process_question_probe(self, question_id: int, model: str = None) -> dict:
        """Run only probe/normalization and knowledge analysis for one question."""
        from apps.parser.models import ExamQuestion

        question = ExamQuestion.objects.get(id=question_id)
        results = {}
        errors = {}
        image_urls = self._get_question_image_urls(question)

        try:
            probe_result = self.probe_and_norm(question, image_urls, model=model)
            results['probe'] = probe_result
            normalized_text = probe_result.get('normalized_text', question.stem or '')
        except AIRequestError as error:
            errors['probe'] = str(error)
            results['probe'] = {'error': str(error)}
            normalized_text = question.stem or ''

        try:
            results['knowledge'] = self.analyze_knowledge_points(
                question,
                normalized_text,
                subject_hint=results['probe'].get('subject', ''),
                model=model,
            )
        except AIRequestError as error:
            errors['knowledge'] = str(error)
            results['knowledge'] = {'error': str(error)}

        results['errors'] = errors
        return results

    def process_question_full_v2(
        self,
        question_id: int,
        model: str = None,
        on_step_complete=None,
        retry_mode_b: bool = False,
    ) -> dict:
        """Full 6-step pipeline: Probe -> Vision -> Solver A/B/C -> Verifier."""
        from django.utils import timezone
        from apps.parser.models import ExamQuestion

        question = ExamQuestion.objects.get(id=question_id)
        errors = {}
        results = {}

        def notify_step_complete(step_key: str) -> None:
            """Allow durable batch callers to persist each successful step."""
            if on_step_complete is not None:
                on_step_complete(step_key, deepcopy(results[step_key]))

        # Update status to running
        question.ai_processing_status = 'running'
        question.save(update_fields=['ai_processing_status'])

        # Get image URLs
        image_urls = self._get_question_image_urls(question)
        logger.info(f'[AI] Got {len(image_urls)} image URLs for question {question_id}')
        input_hash = self._processing_input_hash(question, image_urls, model)

        # Step 1: Probe & Norm
        probe_result = self._cached_pipeline_result(
            getattr(question, "ai_probe_result", None), input_hash
        )
        if probe_result is not None:
            results['probe'] = probe_result
            normalized_text = probe_result.get('normalized_text', question.stem or '')
        else:
            try:
                probe_result = self.probe_and_norm(question, image_urls, model=model)
                probe_result = self._with_pipeline_cache(probe_result, input_hash)
                normalized_text = probe_result.get('normalized_text', question.stem or '')
                results['probe'] = probe_result
            except AIRequestError as e:
                errors['probe'] = str(e)
                results['probe'] = {'error': str(e)}
                normalized_text = question.stem or ''
        if not results['probe'].get('error'):
            notify_step_complete('probe')

        # Step 1.5: Knowledge analysis（识别 1-5 个知识点 + 难度，供 save 匹配并更新）
        knowledge = self._cached_pipeline_result(
            getattr(question, "ai_knowledge_enrichment", None), input_hash
        )
        if knowledge is not None:
            results['knowledge'] = knowledge
        else:
            try:
                knowledge = self.analyze_knowledge_points(
                    question, normalized_text,
                    subject_hint=results.get('probe', {}).get('subject', ''),
                    model=model,
                )
                results['knowledge'] = self._with_pipeline_cache(knowledge, input_hash)
            except AIRequestError as e:
                errors['knowledge'] = str(e)
                results['knowledge'] = {'error': str(e)}
        if not results['knowledge'].get('error'):
            notify_step_complete('knowledge')

        # Step 2: Vision Extraction
        vision_result = self._cached_pipeline_result(
            getattr(question, "ai_vision_extract", None), input_hash
        )
        if vision_result is not None:
            results['vision'] = vision_result
        else:
            try:
                vision_result = self.vision_extraction(
                    question, image_urls, normalized_text, model=model
                )
                vision_result = self._with_pipeline_cache(vision_result, input_hash)
                results['vision'] = vision_result
            except AIRequestError as e:
                errors['vision'] = str(e)
                results['vision'] = {'error': str(e)}
                vision_result = {}
        if not results['vision'].get('error'):
            notify_step_complete('vision')

        vision_for_ai = self._without_pipeline_cache_metadata(vision_result)

        # Build knowledge refs
        knowledge_refs = ""
        if results.get('probe', {}).get('topic_tags_top3'):
            knowledge_refs = ", ".join(results['probe']['topic_tags_top3'])

        # A blank source answer must first become a durable DeepSeek canonical
        # baseline.  The A/B/C generators then compare only their final answer
        # with that baseline; their intentionally different teaching processes
        # are never compared.
        # ExamQuestion always has ``answer``.  Keep lightweight compatibility
        # callers that provide only a question-like object on the legacy path.
        source_answer = getattr(question, 'answer', object())
        unanswered = source_answer is None or (
            isinstance(source_answer, str) and not source_answer.strip()
        )
        baseline = None
        if unanswered:
            try:
                baseline = self.solve_unanswered_question_baseline(
                    question,
                    image_urls=image_urls,
                    normalized_text=normalized_text,
                    vision_result=vision_for_ai,
                    knowledge_refs=knowledge_refs,
                )
                question.answer = baseline['canonical_answer']
                question.analysis = baseline['canonical_analysis']
                results['baseline'] = baseline
                notify_step_complete('baseline')
            except AIRequestError as error:
                errors['baseline'] = str(error)
                results['baseline'] = {'error': str(error)}
                results['errors'] = errors
                results['image_count'] = len(image_urls)
                question.ai_processing_status = 'failed'
                question.ai_processed_at = timezone.now()
                question.save(update_fields=['ai_processing_status', 'ai_processed_at'])
                return results

        # Step 3: Solver A/B/C with independent verification and arbitration.
        shared_verification = None if baseline is not None else self._cached_shared_verification(
            question,
            image_urls=image_urls,
            normalized_text=normalized_text,
            vision_result=vision_for_ai,
            knowledge_refs=knowledge_refs,
        )
        for mode in "ABC":
            answer_key = f"answer_{mode.lower()}"
            attempts = 2 if retry_mode_b and mode == 'B' else 1
            for attempt in range(attempts):
                try:
                    if baseline is not None:
                        outcome = self.solve_unanswered_mode_with_arbitration(
                            question,
                            mode=mode,
                            baseline=baseline,
                            image_urls=image_urls,
                            normalized_text=normalized_text,
                            vision_result=vision_for_ai,
                            knowledge_refs=knowledge_refs,
                            model=model,
                        )
                    else:
                        outcome = self.solve_mode_with_arbitration(
                            question,
                            mode=mode,
                            image_urls=image_urls,
                            normalized_text=normalized_text,
                            vision_result=vision_for_ai,
                            knowledge_refs=knowledge_refs,
                            cached_verification=shared_verification,
                            model=model,
                        )
                    answer = dict(outcome.answer)
                    route_provider, route_model = self._task_route(
                        f"mode_{mode.lower()}_answer"
                    )
                    answer['provider'] = route_provider
                    answer['model'] = route_model
                    results[answer_key] = answer
                    if outcome.shared_verifier_result is not None:
                        shared_verification = _safe_shared_verifier_result(
                            outcome.shared_verifier_result
                        )
                    notify_step_complete(answer_key)
                    break
                except (AIRequestError, ArbitrationError) as error:
                    if attempt + 1 < attempts:
                        logger.warning(
                            'AI mode B retrying after recoverable processing failure',
                            extra={'question_id': str(question_id), 'mode': mode},
                        )
                        continue
                    failure = _safe_arbitration_failure(error)
                    errors[answer_key] = failure
                    results[answer_key] = {'error': failure}

        if shared_verification is not None and not errors:
            results['verifier'] = deepcopy(shared_verification)

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
                        kp['id'] = str(db_kp.id)
                        kp['module'] = db_kp.module
                        kp['full_label'] = db_kp.full_label
                        matched_kps.append({'id': str(db_kp.id), 'module': db_kp.module})
                        logger.info(
                            '[AI] knowledge point matched',
                            extra={'status': 'matched'},
                        )
                    else:
                        kp['id'] = None
                        kp['full_label'] = ai_module
                        logger.info(
                            '[AI] knowledge point unmatched',
                            extra={'status': 'unmatched'},
                        )
            question.ai_knowledge_enrichment = kp_data
            # 用匹配到 DB 的知识点更新题目的 knowledge_points 关联
            # No match means the question belongs to the virtual root/未分类 node.
            # Clear stale associations when re-running AI, so the tree and question
            # query remain consistent with the latest AI result.
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

        # The no-answer baseline is safe structured data.  Persist it with the
        # canonical answer/analysis immediately, independently of later modes.
        if 'baseline' in results and not results['baseline'].get('error'):
            baseline = results['baseline']
            question.answer = baseline['canonical_answer']
            question.analysis = baseline['canonical_analysis']
            question.ai_verifier_result = {
                'unanswered_baseline': {
                    key: deepcopy(baseline[key])
                    for key in ('canonical_answer', 'canonical_analysis', 'key_facts', 'confidence', 'context_hash')
                    if key in baseline
                }
            }

        # Save only the shared DeepSeek verification cache. Legacy verifier
        # envelopes and partial/failed runs must preserve the previous cache.
        safe_verifier = (
            _safe_shared_verifier_result(results.get('verifier'))
            if not results.get('errors')
            else None
        )
        if safe_verifier is not None:
            question.ai_verifier_result = safe_verifier

        # Save A/B/C answers (existing logic)
        if 'answer_a' in results and not results['answer_a'].get('error'):
            question.ai_answer_a = results['answer_a']
        if 'answer_b' in results and not results['answer_b'].get('error'):
            question.ai_answer_b = results['answer_b']
        if 'answer_c' in results and not results['answer_c'].get('error'):
            question.ai_answer_c = results['answer_c']

        question.save()

        logger.info(
            '[AI SAVE] question fields persisted',
            extra={
                'question_id': str(question_id),
                'answer_a_present': bool(question.ai_answer_a),
                'answer_b_present': bool(question.ai_answer_b),
                'answer_c_present': bool(question.ai_answer_c),
            },
        )


def create_ai_review_service(**kwargs) -> AIReviewService:
    """Build the compatibility facade through one injectable entry point."""
    return AIReviewService(**kwargs)
