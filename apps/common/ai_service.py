"""Backward-compatible facade for the shared question AI components."""
from copy import deepcopy
import json
import logging
import time
import os
import threading
import re
from decimal import Decimal
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
    TaxonomyKnowledgeComponent,
    TaxonomyScopeComponent,
    TaxonomySubtopicComponent,
    ResultVerifierComponent,
    VisionExtractionComponent,
)
from apps.common.ai.answer_arbitration import (
    ArbitrationError,
    ArbitrationOutcome,
    ArbitrationProviderError,
    ModeAnswerArbitrator,
)
from apps.common.ai.answer_validation import AnswerNormalizer
from apps.common.ai.question_context import (
    QuestionContextBuilder,
    question_context_hash,
    question_context_payload,
)
from apps.common.ai.schemas import (
    ModeAResponse,
    ModeBResponse,
    ModeCResponse,
    mode_response_schema,
    multipart_true_false_labels,
)
from apps.knowledge.controlled_catalog import (
    ControlledCatalogSelectionError,
    child_topic_candidates,
    leaf_knowledge_candidates,
    root_topic_candidates,
    validate_selected_ids,
)

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
_TRUE_FALSE_CANONICAL_TOKENS = (
    ("FALSE", re.compile(r"\bfalse\b|错误|\bwrong\b|[×✗]", re.IGNORECASE)),
    ("TRUE", re.compile(r"\btrue\b|正确|\bcorrect\b|[√✓]", re.IGNORECASE)),
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

    @staticmethod
    def _probe_source_text(question) -> str:
        """Keep multipart/table context instead of reducing a question to its stem."""
        stem = str(getattr(question, "stem", "") or "")
        context = QuestionContextBuilder.build(question)
        material = str(getattr(question, "material", "") or "")
        tables = context.metadata.get("tables", ())
        subquestions = context.metadata.get("subquestions", ())
        has_structured_context = bool(
            material or context.options or tables or subquestions
        )
        if stem.strip() and not has_structured_context:
            return stem

        payload = {
            "stem": stem,
            "material": material,
            "subject": str(getattr(question, "subject", "") or ""),
            "question_type": str(
                getattr(question, "question_type", "")
                or getattr(question, "source_question_type", "")
                or ""
            ),
            "options": context.options,
            "tables": tables,
            "subquestions": subquestions,
        }
        if not stem.strip():
            payload["raw_text"] = str(getattr(question, "raw_text", "") or "")
        rendered = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return rendered[:30000]

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
        probe_text = self._probe_source_text(question)
        if probe_text != question_input.stem:
            question_input = QuestionInput(
                stem=probe_text,
                options=question_input.options,
                answer=question_input.answer,
                solution=question_input.solution,
                image_urls=question_input.image_urls,
                metadata=question_input.metadata,
            )
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
        exclude_reference_answer=False,
    ) -> dict:
        """Create the canonical answer/analysis baseline for a question without one."""
        context = QuestionContextBuilder.build(
            question,
            image_urls=image_urls,
            normalized_text=normalized_text,
            vision_result=vision_result,
            knowledge_refs=knowledge_refs,
        )
        if exclude_reference_answer:
            # A historical generated baseline can be syntactically invalid for
            # an objective question.  Do not feed that faulty answer back to
            # the independent DeepSeek solve which is supposed to replace it.
            context = QuestionInput(
                stem=context.stem,
                options=context.options,
                answer="",
                solution="",
                image_urls=context.image_urls,
                metadata={
                    **context.metadata,
                    "reference_analysis": "",
                },
            )
        component = self._component(DeepSeekBaselineSolveComponent)
        for _attempt in range(2):
            result = self._run_component(component, context)
            normalized_answer = self._normalize_unanswered_baseline_answer(
                context,
                result.get("canonical_answer"),
                allow_new_true_false_explanation=True,
            )
            if result["confidence"] >= 0.80 and normalized_answer is not None:
                return {
                    **result,
                    "canonical_answer": normalized_answer,
                    "context_hash": question_context_hash(context),
                }
        raise AIRequestError("baseline_invalid")

    @staticmethod
    def _normalize_unanswered_baseline_answer(
        context,
        answer: object,
        *,
        allow_new_true_false_explanation=False,
    ) -> str | None:
        """Return a canonical answer only when it satisfies the question contract.

        A high model confidence is not enough for objective questions.  Historic
        rows show that an explanatory sentence can be persisted as a judgment
        or choice answer; then every later A/B/C arbitration fails before it
        reaches a provider.  Keep the same deterministic normalizer used by
        arbitration so new and persisted baselines have one validity boundary.
        """
        payload = question_context_payload(context)
        option_labels = tuple(
            item.get("label", "")
            for item in payload.get("options", ())
            if isinstance(item, dict)
        )
        normalized = AnswerNormalizer().normalize(
            answer,
            question_type=payload.get("question_type", ""),
            option_labels=option_labels,
            subquestion_labels=multipart_true_false_labels(
                payload.get("question_type", ""), payload.get("subquestions", ())
            ),
        )
        if normalized.valid:
            return normalized.value
        if not allow_new_true_false_explanation or not isinstance(answer, str):
            return None
        if payload.get("question_type", "").strip().casefold() not in {
            "true_false",
            "judgement",
            "judgment",
            "判断题",
        }:
            return None
        # Models occasionally return a semantically unambiguous presentation
        # variant such as ``TRUE（正确）``.  This narrow fallback is for a fresh
        # DeepSeek result only; persisted historical baselines continue through
        # the strict normalizer above and are regenerated when malformed.
        matches = {
            canonical
            for canonical, pattern in _TRUE_FALSE_CANONICAL_TOKENS
            if pattern.search(answer)
        }
        return next(iter(matches)) if len(matches) == 1 else None

    def unanswered_baseline_is_valid(
        self,
        question,
        baseline: object,
        *,
        image_urls=(),
        normalized_text="",
        vision_result=None,
        knowledge_refs="",
    ) -> bool:
        """Validate a persisted no-answer baseline before reusing it.

        This intentionally validates only the canonical answer shape.  Analysis
        remains free-form, while choice/judgment answer notation must be safe
        for the shared arbitrator.  It is used for legacy records whose answer
        field is no longer blank because a previous baseline was persisted.
        """
        if not isinstance(baseline, dict):
            return False
        if not isinstance(baseline.get("canonical_analysis"), str) or not baseline[
            "canonical_analysis"
        ].strip():
            return False
        context = QuestionContextBuilder.build(
            question,
            image_urls=image_urls,
            normalized_text=normalized_text,
            vision_result=vision_result,
            knowledge_refs=knowledge_refs,
        )
        return self._normalize_unanswered_baseline_answer(
            context, baseline.get("canonical_answer")
        ) is not None

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
                    response_schema = mode_response_schema(
                        normalized_mode,
                        question_type=context.metadata.get("question_type", ""),
                        subquestions=context.metadata.get("subquestions", ()),
                    )
                    if response_schema is None:
                        raise ValidationError.from_exception_data("mode schema", [])
                    validated_answer = response_schema.model_validate(outcome.answer)
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
            response_schema = mode_response_schema(
                normalized_mode,
                question_type=context.metadata.get("question_type", ""),
                subquestions=context.metadata.get("subquestions", ()),
            )
            if response_schema is None:
                raise ValidationError.from_exception_data("mode schema", [])
            validated_answer = response_schema.model_validate(outcome.answer)
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

    @staticmethod
    def _controlled_scope_candidate(scope_result: dict, candidates: list[dict]) -> dict:
        candidate_by_id = {
            str(candidate.get('id')): candidate for candidate in candidates
        }
        topic_id = str(scope_result.get('topic_id') or '')
        candidate = candidate_by_id.get(topic_id)
        if candidate is None:
            raise AIRequestError('controlled taxonomy scope selected an unknown topic')
        if (
            scope_result.get('subject') != candidate.get('subject')
            or scope_result.get('stage') != candidate.get('stage')
        ):
            raise AIRequestError('controlled taxonomy scope does not match selected topic')
        return candidate

    @staticmethod
    def _controlled_subtopic_candidate(
        subtopic_result: dict,
        candidates: list[dict],
    ) -> dict:
        candidate_by_id = {
            str(candidate.get('id')): candidate for candidate in candidates
        }
        subtopic_id = str(subtopic_result.get('subtopic_id') or '')
        candidate = candidate_by_id.get(subtopic_id)
        if candidate is None:
            raise AIRequestError('controlled taxonomy subtopic selected an unknown topic')
        return candidate

    def _run_controlled_taxonomy_scope(self, question, image_urls: list) -> tuple[dict, dict]:
        candidates = root_topic_candidates()
        if not candidates:
            raise AIRequestError('controlled taxonomy catalog has no root topics')
        result = self._run_component(
            self._component(TaxonomyScopeComponent),
            QuestionInput(
                stem=self._probe_source_text(question),
                options=self._question_input(question, image_urls).options,
                answer=getattr(question, 'answer', '') or '',
                solution=getattr(question, 'solution', '') or '',
                image_urls=tuple(image_urls),
                metadata={'topic_candidates': candidates},
            ),
        )
        candidate = self._controlled_scope_candidate(result, candidates)
        result['topic_path_ids'] = candidate['path_ids']
        result['catalog_version'] = self._catalog_version(candidate)
        return result, candidate

    @staticmethod
    def _catalog_version(candidate: dict) -> str:
        """Read the version persisted on the selected controlled topic."""
        from apps.knowledge.models import KnowledgeTopic

        return str(
            KnowledgeTopic.objects.filter(id=str(candidate['id'])).values_list(
                'catalog_version', flat=True
            ).first() or ''
        )

    def _run_controlled_taxonomy_subtopic(
        self,
        question,
        scope: dict,
        selected_scope: dict,
    ) -> tuple[dict, dict]:
        candidates = child_topic_candidates(str(selected_scope['id']))
        if not candidates:
            return {
                'subtopic_id': None,
                'confidence': 1.0,
                'skipped': True,
            }, selected_scope
        result = self._run_component(
            self._component(TaxonomySubtopicComponent),
            QuestionInput(
                stem=str(scope['normalized_text']),
                metadata={
                    'normalized_text': scope['normalized_text'],
                    'scope': scope,
                    'subtopic_candidates': candidates,
                },
            ),
        )
        candidate = self._controlled_subtopic_candidate(result, candidates)
        result['topic_path_ids'] = candidate['path_ids']
        return result, candidate

    def _run_controlled_taxonomy_knowledge(
        self,
        question,
        scope: dict,
        selected_topic: dict,
        image_urls: list,
    ) -> dict:
        candidates = leaf_knowledge_candidates(str(selected_topic['id']))
        if not candidates:
            raise AIRequestError('controlled taxonomy topic has no knowledge modules')
        result = self._run_component(
            self._component(TaxonomyKnowledgeComponent),
            QuestionInput(
                stem=str(scope['normalized_text']),
                options=self._question_input(question, image_urls).options,
                image_urls=tuple(image_urls),
                metadata={
                    'normalized_text': scope['normalized_text'],
                    'scope': {
                        **scope,
                        'selected_topic_id': selected_topic['id'],
                        'selected_topic_name': selected_topic['name'],
                    },
                    'candidates': candidates,
                    'difficulty_level': scope['difficulty_level'],
                },
            ),
        )
        try:
            result['knowledge_modules'] = validate_selected_ids(
                [candidate['id'] for candidate in candidates],
                result['knowledge_modules'],
            )
        except ControlledCatalogSelectionError as error:
            raise AIRequestError(str(error)) from error
        result['selected_topic_id'] = str(selected_topic['id'])
        result['catalog_version'] = self._catalog_version(selected_topic)
        return result

    def _persist_controlled_probe_stage(self, question_id, taxonomy: dict) -> None:
        self.save_results_to_question(
            question_id,
            {'controlled_taxonomy': taxonomy, 'errors': {}},
        )

    def _process_legacy_question_probe(self, question, image_urls, model=None) -> dict:
        """Keep historic rows processable until the controlled catalog is imported."""
        results = {}
        errors = {}
        try:
            probe_result = self.probe_and_norm(question, image_urls, model=model)
            results['probe'] = probe_result
            normalized_text = probe_result.get('normalized_text', question.stem or '')
        except AIRequestError as error:
            errors['probe'] = str(error)
            results['probe'] = {'error': str(error)}
            if str(error) == 'invalid_question_type':
                question.review_status = 'need_review'
                question.save(update_fields=['review_status'])
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

    def process_question_probe(
        self,
        question_id: int,
        model: str = None,
        on_step_complete=None,
    ) -> dict:
        """Run the controlled three-stage probe and save each stage immediately."""
        from apps.parser.models import ExamQuestion

        question = ExamQuestion.objects.get(id=question_id)
        if not root_topic_candidates():
            return self._process_legacy_question_probe(
                question,
                self._get_question_image_urls(question),
                model=model,
            )
        results: dict = {'controlled_taxonomy': {}}
        errors: dict = {}
        image_urls = self._get_question_image_urls(question)

        try:
            scope, selected_scope = self._run_controlled_taxonomy_scope(
                question, image_urls
            )
            results['controlled_taxonomy']['scope'] = scope
            self._persist_controlled_probe_stage(
                question_id, {'scope': scope}
            )
            if on_step_complete is not None:
                on_step_complete('taxonomy_scope', deepcopy(scope))
        except AIRequestError as error:
            errors['taxonomy_scope'] = str(error)
            results['controlled_taxonomy']['scope'] = {'error': str(error)}
            results['errors'] = errors
            return results

        try:
            subtopic, selected_topic = self._run_controlled_taxonomy_subtopic(
                question, scope, selected_scope
            )
            results['controlled_taxonomy']['subtopic'] = subtopic
            self._persist_controlled_probe_stage(
                question_id, {'subtopic': subtopic}
            )
            if on_step_complete is not None:
                on_step_complete('taxonomy_subtopic', deepcopy(subtopic))
        except AIRequestError as error:
            errors['taxonomy_subtopic'] = str(error)
            results['controlled_taxonomy']['subtopic'] = {'error': str(error)}
            results['errors'] = errors
            return results

        try:
            knowledge = self._run_controlled_taxonomy_knowledge(
                question, scope, selected_topic, image_urls
            )
            results['controlled_taxonomy']['knowledge'] = knowledge
            self._persist_controlled_probe_stage(
                question_id, {'knowledge': knowledge}
            )
            if on_step_complete is not None:
                on_step_complete('taxonomy_knowledge', deepcopy(knowledge))
        except AIRequestError as error:
            errors['taxonomy_knowledge'] = str(error)
            results['controlled_taxonomy']['knowledge'] = {'error': str(error)}

        question.refresh_from_db()
        results['probe'] = deepcopy(question.ai_probe_result or {})
        results['knowledge'] = deepcopy(question.ai_knowledge_enrichment or {})

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

        controlled_catalog_ready = bool(root_topic_candidates())
        if controlled_catalog_ready:
            # The controlled stages save scope, subtopic, and selected modules
            # independently before the answer pipeline continues.
            controlled_probe = self.process_question_probe(question_id, model=model)
            if 'controlled_taxonomy' in controlled_probe:
                results['controlled_taxonomy'] = controlled_probe['controlled_taxonomy']
            results['probe'] = controlled_probe.get('probe', {})
            results['knowledge'] = controlled_probe.get('knowledge', {})
            errors.update(controlled_probe.get('errors', {}))
            normalized_text = results['probe'].get(
                'normalized_text', question.stem or ''
            )
        else:
            # Until the catalog exists, retain the established cached legacy
            # path.  This prevents historic AI results from causing another
            # model call merely because the new feature was deployed.
            probe_result = self._cached_pipeline_result(
                getattr(question, 'ai_probe_result', None), input_hash
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
                except AIRequestError as error:
                    errors['probe'] = str(error)
                    results['probe'] = {'error': str(error)}
                    normalized_text = question.stem or ''
            if not results['probe'].get('error'):
                notify_step_complete('probe')

            knowledge = self._cached_pipeline_result(
                getattr(question, 'ai_knowledge_enrichment', None), input_hash
            )
            if knowledge is not None:
                results['knowledge'] = knowledge
            else:
                try:
                    knowledge = self.analyze_knowledge_points(
                        question,
                        normalized_text,
                        subject_hint=results.get('probe', {}).get('subject', ''),
                        model=model,
                    )
                    results['knowledge'] = self._with_pipeline_cache(knowledge, input_hash)
                except AIRequestError as error:
                    errors['knowledge'] = str(error)
                    results['knowledge'] = {'error': str(error)}
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
        if results.get('knowledge', {}).get('knowledge_modules'):
            knowledge_refs = ", ".join(
                results['knowledge']['knowledge_modules']
            )
        elif results.get('probe', {}).get('topic_tags_top3'):
            # Historic cached probe envelopes store free-text tags rather
            # than the new controlled module list.
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

    def _save_controlled_taxonomy(self, question, taxonomy_update: dict) -> None:
        """Persist one controlled probe stage without discarding earlier stages."""
        from apps.knowledge.models import KnowledgePoint, KnowledgeTopic

        probe = deepcopy(question.ai_probe_result) if isinstance(
            question.ai_probe_result, dict
        ) else {}
        taxonomy = deepcopy(probe.get('taxonomy')) if isinstance(
            probe.get('taxonomy'), dict
        ) else {}
        for stage_name, value in taxonomy_update.items():
            if isinstance(value, dict) and not value.get('error'):
                taxonomy[stage_name] = deepcopy(value)
        probe['taxonomy'] = taxonomy

        scope = taxonomy.get('scope')
        if isinstance(scope, dict):
            for key in ('subject', 'stage', 'question_type', 'difficulty_level', 'normalized_text'):
                value = scope.get(key)
                if isinstance(value, str) and value.strip():
                    probe[key] = value
            from apps.common.question_types import (
                normalize_question_type,
                require_ai_question_type,
            )

            question_type = normalize_question_type(
                probe.get('question_type'),
                stem=question.stem,
                options=getattr(question, 'options', None),
                answer=question.answer,
            )
            try:
                question.question_type = require_ai_question_type(question_type)
            except ValueError:
                question.review_status = 'need_review'
                raise AIRequestError('invalid_question_type') from None
            probe['question_type'] = question.question_type
            subject = probe.get('subject')
            if subject in {'math', 'physics'}:
                question.subject = subject
            level = probe.get('difficulty_level')
            if level in {'L1', 'L2', 'L3', 'L4', 'L5'}:
                question.difficulty_level = level

        knowledge = taxonomy.get('knowledge')
        if isinstance(knowledge, dict):
            selected_topic_id = knowledge.get('selected_topic_id')
            selected_modules = knowledge.get('knowledge_modules')
            if (
                isinstance(selected_topic_id, str)
                and isinstance(selected_modules, list)
                and selected_modules
            ):
                topic = KnowledgeTopic.objects.filter(
                    id=selected_topic_id,
                    is_enabled=True,
                ).first()
                if topic is None:
                    raise AIRequestError('controlled taxonomy selected topic no longer exists')
                modules = [str(module).strip() for module in selected_modules]
                points_by_module = {}
                for point in KnowledgePoint.objects.filter(
                    subject=topic.subject,
                    stage=topic.stage,
                    chapter=topic.name,
                    module__in=modules,
                ).order_by('id'):
                    points_by_module.setdefault(point.module, point)
                missing = [module for module in modules if module not in points_by_module]
                if missing:
                    raise AIRequestError(
                        'controlled taxonomy selected module is no longer in local tree'
                    )
                matched_points = [points_by_module[module] for module in modules]
                final_point = matched_points[-1]
                derived_taxonomy = {
                    'subject': final_point.subject,
                    'stage': final_point.stage,
                    'grade_index': final_point.grade_index,
                    'grade': final_point.grade_name,
                    'semester': KnowledgePoint.TERM_LABELS.get(
                        final_point.term, final_point.term
                    ),
                    'term': final_point.term,
                    'chapter': final_point.chapter,
                    'knowledge_point_id': str(final_point.id),
                    'knowledge_point_module': final_point.module,
                }
                probe['derived_taxonomy'] = derived_taxonomy
                probe.update({
                    'subject': derived_taxonomy['subject'],
                    'stage': derived_taxonomy['stage'],
                    'grade': derived_taxonomy['grade'],
                    'semester': derived_taxonomy['semester'],
                    'chapter': derived_taxonomy['chapter'],
                })
                question.subject = derived_taxonomy['subject']
                question.knowledge_points = [
                    {'id': str(point.id), 'module': point.module}
                    for point in matched_points
                ]
                level = probe.get('difficulty_level')
                score = knowledge.get('difficulty_score')
                if level in {'L1', 'L2', 'L3', 'L4', 'L5'} and score is not None:
                    score_decimal = Decimal(str(score)).quantize(Decimal('0.01'))
                    lower = Decimal(level[1])
                    if not lower <= score_decimal <= lower + Decimal('0.9'):
                        raise AIRequestError(
                            'controlled taxonomy difficulty score is outside the selected difficulty level'
                        )
                    question.difficulty_level = level
                    question.difficulty = score_decimal
                question.ai_knowledge_enrichment = {
                    'knowledge_modules': modules,
                    'difficulty_level': question.difficulty_level,
                    'difficulty_score': float(question.difficulty)
                    if question.difficulty is not None else None,
                    'difficulty_reason': knowledge.get('difficulty_reason', ''),
                    'confidence': knowledge.get('confidence'),
                    'selected_topic_id': selected_topic_id,
                    'derived_taxonomy': derived_taxonomy,
                }

        question.ai_probe_result = probe
        question.save()

    def save_results_to_question(self, question_id: int, results: dict):
        """Save AI processing results to ExamQuestion record.

        Also matches knowledge point IDs against the knowledge_points table.
        """
        from apps.parser.models import ExamQuestion
        from apps.knowledge.models import KnowledgePoint

        question = ExamQuestion.objects.get(id=question_id)

        controlled_taxonomy = results.get('controlled_taxonomy')
        if isinstance(controlled_taxonomy, dict):
            self._save_controlled_taxonomy(question, controlled_taxonomy)
            remaining_keys = {
                key for key in results
                if key not in {'controlled_taxonomy', 'probe', 'knowledge', 'errors'}
            }
            if not remaining_keys:
                return
            results = {
                key: value
                for key, value in results.items()
                if key not in {'controlled_taxonomy', 'probe', 'knowledge'}
            }
            question.refresh_from_db()

        # The local knowledge tree, rather than the probe model, owns grade,
        # term, and chapter.  A probe may already have been saved by an
        # earlier per-step write, so enrich that persisted value when the
        # knowledge step arrives on its own.
        probe_data = results.get('probe')
        if not isinstance(probe_data, dict):
            probe_data = getattr(question, 'ai_probe_result', None)
        if not isinstance(probe_data, dict):
            probe_data = None

        # Determine matching subject from the current knowledge result first,
        # then the probe, and only finally the pre-existing question record.
        subject_map = {'math': 'math', 'physics': 'physics', '数学': 'math', '物理': 'physics'}
        probe_subject = subject_map.get(
            (probe_data or {}).get('subject', ''),
            '',
        )
        question_subject = probe_subject or subject_map.get(question.subject, '')
        derived_taxonomy = None

        # Enrich knowledge points with actual DB records
        # Validate and correct: AI may return a wrong id that doesn't match the module name
        if 'knowledge' in results and results['knowledge'].get('error') is None:
            kp_data = results['knowledge']
            matched_kps = []
            matched_points = []
            if kp_data.get('knowledge_points'):
                for kp in kp_data['knowledge_points']:
                    ai_module = (kp.get('module') or '').strip()
                    kp_subject = subject_map.get(
                        (kp.get('subject') or kp_data.get('subject') or question_subject).strip(),
                        question_subject,
                    )
                    if not ai_module:
                        continue
                    # 匹配 knowledge_points 表的 module 字段：精确 -> 模糊 contains（同 subject 优先，再跨 subject）
                    db_kp = None
                    if kp_subject:
                        db_kp = KnowledgePoint.objects.filter(subject=kp_subject, module=ai_module).first()
                    if not db_kp and kp_subject:
                        db_kp = KnowledgePoint.objects.filter(subject=kp_subject, module__icontains=ai_module).first()
                    if not db_kp:
                        db_kp = KnowledgePoint.objects.filter(module__icontains=ai_module).first()
                    if db_kp:
                        kp['id'] = str(db_kp.id)
                        kp['module'] = db_kp.module
                        kp['full_label'] = db_kp.full_label
                        kp['local_taxonomy'] = {
                            'subject': db_kp.subject,
                            'stage': db_kp.stage,
                            'grade_index': db_kp.grade_index,
                            'grade': db_kp.grade_name,
                            'semester': KnowledgePoint.TERM_LABELS.get(db_kp.term, db_kp.term),
                            'term': db_kp.term,
                            'chapter': db_kp.chapter,
                        }
                        matched_kps.append({'id': str(db_kp.id), 'module': db_kp.module})
                        matched_points.append(db_kp)
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
            if matched_points:
                final_point = matched_points[-1]
                derived_taxonomy = {
                    'subject': final_point.subject,
                    'stage': final_point.stage,
                    'grade_index': final_point.grade_index,
                    'grade': final_point.grade_name,
                    'semester': KnowledgePoint.TERM_LABELS.get(final_point.term, final_point.term),
                    'term': final_point.term,
                    'chapter': final_point.chapter,
                    'knowledge_point_id': str(final_point.id),
                    'knowledge_point_module': final_point.module,
                }
            else:
                derived_taxonomy = {}
            kp_data['derived_taxonomy'] = derived_taxonomy
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

        # Keep the probe's core classification, but make all taxonomy values
        # authoritative only after the local knowledge point match is known.
        if isinstance(results.get('probe'), dict) and not results['probe'].get('error'):
            from apps.common.question_types import normalize_question_type

            raw_question_type = results['probe'].get('question_type')
            question_type = normalize_question_type(
                raw_question_type,
                stem=question.stem,
                options=getattr(question, 'options', None),
                answer=question.answer,
            )
            try:
                from apps.common.question_types import require_ai_question_type

                question_type = require_ai_question_type(question_type)
            except ValueError:
                question.review_status = 'need_review'
                results['probe'] = {'error': 'invalid_question_type'}
                probe_data = results['probe']
            else:
                question.question_type = question_type
                if probe_data is not None:
                    probe_data['question_type'] = question_type
        if probe_data is not None:
            probe_data.pop('stage', None)
            probe_data.pop('grade', None)
            probe_data.pop('semester', None)
            probe_data.pop('chapter', None)
            if derived_taxonomy:
                probe_data['derived_taxonomy'] = derived_taxonomy
                probe_data.update({
                    'subject': derived_taxonomy['subject'],
                    'stage': derived_taxonomy['stage'],
                    'grade': derived_taxonomy['grade'],
                    'semester': derived_taxonomy['semester'],
                    'chapter': derived_taxonomy['chapter'],
                })
                question.subject = derived_taxonomy['subject']
            elif derived_taxonomy == {}:
                probe_data['derived_taxonomy'] = {}
            question.ai_probe_result = probe_data

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
