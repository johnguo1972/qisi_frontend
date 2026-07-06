"""AI service for knowledge analysis and A/B/C mode answer generation."""
import json
import logging
import time
import os
import httpx
from django.conf import settings
from apps.common.exceptions import AIRequestError
from apps.common.ai_prompts import AIPrompts
from apps.common.utils import repair_json_string

logger = logging.getLogger(__name__)

QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


class AIReviewService:
    """Service for AI-powered knowledge analysis and answer generation."""

    def __init__(self):
        self.api_key = os.environ.get('QWEN_API_KEY', '')
        if not self.api_key:
            raise AIRequestError("QWEN_API_KEY is not set")

    def _get_model(self, override_model: str = None, *, default_model: str = None) -> str:
        """Get AI model name, with optional override and per-call default.

        Priority: override_model > settings.AI_MODEL > default_model fallback.
        """
        return override_model or getattr(settings, 'AI_MODEL', default_model or 'qwen3.6-plus')

    def _call_ai(self, system_prompt: str, user_prompt: str,
                 model: str = None, max_tokens: int = 4000,
                 default_model: str = None) -> str:
        """Call AI API with retry logic (up to 3 attempts).

        Returns: parsed assistant message content (JSON string)
        Raises: AIRequestError on final failure
        """
        model = self._get_model(model, default_model=default_model)
        # Retry delays: 5s → 8s → 10s
        retry_delays = [5, 8, 10]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(1, 4):
            try:
                with httpx.Client(timeout=300.0, trust_env=False) as client:
                    response = client.post(QWEN_API_URL, json=payload, headers=headers)
                    response.raise_for_status()
                result = response.json()
                choices = result.get("choices", [])
                if not choices:
                    raise AIRequestError("No choices in AI response")
                return choices[0]["message"]["content"]
            except httpx.ReadTimeout as e:
                last_error = e
                wait = retry_delays[attempt - 1]
                logger.warning(f"AI API timeout (attempt {attempt}/3), retrying in {wait}s: {e}")
                time.sleep(wait)
            except httpx.HTTPError as e:
                last_error = e
                wait = retry_delays[attempt - 1]
                logger.warning(f"AI API HTTP error (attempt {attempt}/3), retrying in {wait}s: {e}")
                time.sleep(wait)
            except Exception as e:
                raise AIRequestError(f"Unexpected AI API error: {e}")

        raise AIRequestError(f"AI API call failed after 3 attempts: {last_error}")

    def _call_ai_multimodal(self, system_prompt: str, user_text: str,
                            image_urls: list, model: str = None,
                            max_tokens: int = 8000,
                            default_model: str = None) -> str:
        """Call AI API with multimodal (text + images) messages.

        Returns: parsed assistant message content
        Raises: AIRequestError on final failure
        """
        model = self._get_model(model, default_model=default_model)
        retry_delays = [5, 8, 10]

        # Build content parts: text first, then images
        content_parts = [{"type": "text", "text": user_text}]
        for url in image_urls:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": url}
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_parts},
        ]
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(1, 4):
            try:
                with httpx.Client(timeout=300.0, trust_env=False) as client:
                    response = client.post(QWEN_API_URL, json=payload, headers=headers)
                    response.raise_for_status()
                result = response.json()
                choices = result.get("choices", [])
                if not choices:
                    raise AIRequestError("No choices in AI multimodal response")
                return choices[0]["message"]["content"]
            except httpx.ReadTimeout as e:
                last_error = e
                wait = retry_delays[attempt - 1]
                logger.warning(f"AI multimodal timeout (attempt {attempt}/3), retrying in {wait}s: {e}")
                time.sleep(wait)
            except httpx.HTTPError as e:
                last_error = e
                wait = retry_delays[attempt - 1]
                logger.warning(f"AI multimodal HTTP error (attempt {attempt}/3), retrying in {wait}s: {e}")
                time.sleep(wait)
            except Exception as e:
                raise AIRequestError(f"Unexpected AI multimodal error: {e}")

        raise AIRequestError(f"AI multimodal call failed after 3 attempts: {last_error}")

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
        """Upload a file to Aliyun OSS and return the public URL.

        Returns None if OSS is not configured or upload fails.
        """
        import oss2

        access_key_id = os.environ.get('ALIYUN_OSS_ACCESS_KEY_ID', '')
        access_key_secret = os.environ.get('ALIYUN_OSS_ACCESS_KEY_SECRET', '')
        endpoint = os.environ.get('ALIYUN_OSS_ENDPOINT', 'https://oss-cn-shanghai.aliyuncs.com')
        bucket_name = os.environ.get('ALIYUN_OSS_BUCKET', '')

        if not all([access_key_id, access_key_secret, bucket_name]):
            logger.warning('OSS credentials not configured, skipping image upload')
            return None

        try:
            auth = oss2.Auth(access_key_id, access_key_secret)
            bucket = oss2.Bucket(auth, endpoint, bucket_name)

            # Use the file_path as OSS key (e.g., 'exams/11/crops/abc.png')
            with open(local_path, 'rb') as f:
                bucket.put_object(oss_key, f)

            # Return public URL
            url = f'https://{bucket_name}.{endpoint.replace("https://", "")}/{oss_key}'
            logger.info(f'Uploaded to OSS: {url}')
            return url
        except oss2.exceptions.OssError as e:
            logger.error(f'OSS upload failed for {local_path}: {e}')
            return None
        except Exception as e:
            logger.error(f'Unexpected OSS error for {local_path}: {e}')
            return None

    def _parse_json_response(self, raw: str) -> dict:
        """Parse AI JSON response with repair logic."""
        cleaned = repair_json_string(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise AIRequestError(f"Failed to parse AI JSON response: {e}\nRaw: {raw[:500]}")

    def analyze_knowledge(self, question, model: str = None) -> dict:
        """Step 1: Analyze knowledge points for a question.

        Returns: dict with knowledge_points, grade_term, solving_methods
        """
        from apps.knowledge.models import KnowledgePoint
        from apps.parser.models import QuestionImage

        # Build knowledge points list for the prompt
        # Order by stage and grade_index so AI sees all grade levels (not just primary school)
        # Without explicit ordering, ID 1-99 are all primary school, high school starts at ID ~949
        subject_map = {'math': 'math', 'physics': 'physics', '数学': 'math', '物理': 'physics'}
        db_subject = subject_map.get(question.subject, 'math')
        kp_list = list(KnowledgePoint.objects.filter(
            subject=db_subject
        ).order_by('stage', 'grade_index', 'id'))

        # Select representative knowledge points from each grade level
        # so the AI sees the full grade spectrum without exceeding token limits
        selected = []
        seen_grades = {}
        for kp in kp_list:
            grade_key = (kp.stage, kp.grade_index)
            if grade_key not in seen_grades:
                seen_grades[grade_key] = 0
            if seen_grades[grade_key] < 5:  # up to 5 per grade level
                selected.append(kp)
                seen_grades[grade_key] += 1

        kp_list_text = ", ".join(f"[{kp.id}]{kp.module}({kp.full_label})" for kp in selected)

        # Build image descriptions
        images = QuestionImage.objects.filter(question=question).order_by('sort_order')
        image_descs = []
        for img in images:
            image_descs.append(f"图片类型: {img.image_type}, 路径: {img.file_path}")

        prompt = AIPrompts.knowledge_analysis(
            question_text=question.stem,
            question_answer=question.answer or '',
            question_analysis=question.analysis or '',
            question_solution=question.solution or '',
            image_descriptions=image_descs if image_descs else None,
        )
        prompt['user'] = prompt['user'].replace('{knowledge_points_list}', kp_list_text)

        raw = self._call_ai(prompt['system'], prompt['user'], model=model)
        return self._parse_json_response(raw)

    def generate_answer_a(self, question, knowledge_data: dict = None,
                          model: str = None) -> dict:
        """Step 2: Generate A mode answer (3-5 steps) with image attachments."""
        from apps.parser.models import QuestionImage

        knowledge_refs = ""
        if knowledge_data and knowledge_data.get('knowledge_points'):
            kps = knowledge_data['knowledge_points']
            knowledge_refs = ", ".join(
                kp.get('module', '') or kp.get('full_label', '')
                for kp in kps if kp
            )

        # Get image URLs for multimodal
        image_urls = self._get_question_image_urls(question)

        images = QuestionImage.objects.filter(question=question).order_by('sort_order')
        image_descs = [f"图片类型: {img.image_type}" for img in images]

        prompt = AIPrompts.mode_a_answer(
            question_text=question.stem,
            knowledge_refs=knowledge_refs,
            question_answer=question.answer or '',
            question_analysis=question.analysis or '',
            question_solution=question.solution or '',
            image_descriptions=image_descs if image_descs else None,
        )

        if image_urls:
            # Use multimodal API with images
            raw = self._call_ai_multimodal(
                prompt['system'], prompt['user'], image_urls,
                model=model, default_model='qwen3.6-plus'
            )
        else:
            # Fallback to text-only
            raw = self._call_ai(
                prompt['system'], prompt['user'], model=model,
                default_model='qwen3.6-plus'
            )
        return self._parse_json_response(raw)

    def generate_answer_b(self, question, knowledge_data: dict = None,
                          model: str = None) -> dict:
        """Step 3: Generate B mode answer (Socratic multiple-choice) with image attachments."""
        from apps.parser.models import QuestionImage

        knowledge_refs = ""
        if knowledge_data and knowledge_data.get('knowledge_points'):
            kps = knowledge_data['knowledge_points']
            knowledge_refs = ", ".join(
                kp.get('module', '') or kp.get('full_label', '')
                for kp in kps if kp
            )

        # Get image URLs for multimodal
        image_urls = self._get_question_image_urls(question)

        images = QuestionImage.objects.filter(question=question).order_by('sort_order')
        image_descs = [f"图片类型: {img.image_type}" for img in images]

        prompt = AIPrompts.mode_b_answer(
            question_text=question.stem,
            knowledge_refs=knowledge_refs,
            question_answer=question.answer or '',
            question_analysis=question.analysis or '',
            question_solution=question.solution or '',
            image_descriptions=image_descs if image_descs else None,
        )

        if image_urls:
            raw = self._call_ai_multimodal(
                prompt['system'], prompt['user'], image_urls,
                model=model, default_model='qwen3.6-plus'
            )
        else:
            raw = self._call_ai(
                prompt['system'], prompt['user'], model=model,
                default_model='qwen3.6-plus'
            )
        return self._parse_json_response(raw)

    def generate_answer_c(self, question, knowledge_data: dict = None,
                          model: str = None) -> dict:
        """Step 4: Generate C mode answer (Socratic open-ended) with image attachments."""
        from apps.parser.models import QuestionImage

        knowledge_refs = ""
        if knowledge_data and knowledge_data.get('knowledge_points'):
            kps = knowledge_data['knowledge_points']
            knowledge_refs = ", ".join(
                kp.get('module', '') or kp.get('full_label', '')
                for kp in kps if kp
            )

        # Get image URLs for multimodal
        image_urls = self._get_question_image_urls(question)

        images = QuestionImage.objects.filter(question=question).order_by('sort_order')
        image_descs = [f"图片类型: {img.image_type}" for img in images]

        prompt = AIPrompts.mode_c_answer(
            question_text=question.stem,
            knowledge_refs=knowledge_refs,
            question_answer=question.answer or '',
            question_analysis=question.analysis or '',
            question_solution=question.solution or '',
            image_descriptions=image_descs if image_descs else None,
        )

        if image_urls:
            raw = self._call_ai_multimodal(
                prompt['system'], prompt['user'], image_urls,
                model=model, default_model='qwen3.6-plus'
            )
        else:
            raw = self._call_ai(
                prompt['system'], prompt['user'], model=model,
                default_model='qwen3.6-plus'
            )
        return self._parse_json_response(raw)

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
        prompt = AIPrompts.probe_and_norm(
            ocr_text=question.stem or '',
            has_figure=len(image_urls) > 0,
        )

        if image_urls:
            raw = self._call_ai_multimodal(
                prompt['system'], prompt['user'], image_urls,
                model=model, default_model='qwen3.6-flash'
            )
        else:
            raw = self._call_ai(
                prompt['system'], prompt['user'], model=model,
                default_model='qwen3.6-flash'
            )
        return self._parse_json_response(raw)

    def vision_extraction(self, question, image_urls: list,
                          normalized_text: str, model: str = None) -> dict:
        """Step 2: Vision Extraction — 统一读图."""
        prompt = AIPrompts.vision_extraction(normalized_text=normalized_text)

        if image_urls:
            raw = self._call_ai_multimodal(
                prompt['system'], prompt['user'], image_urls,
                model=model, default_model='qwen3.6-plus'
            )
        else:
            raw = self._call_ai(
                prompt['system'], prompt['user'], model=model,
                default_model='qwen3.6-plus'
            )
        return self._parse_json_response(raw)

    def solve_mode_a(self, question, image_urls: list, normalized_text: str,
                     vision_result: dict, knowledge_refs: str,
                     model: str = None) -> dict:
        """Step 3a: A 模式求解."""
        prompt = AIPrompts.solve_mode_a(
            normalized_text=normalized_text,
            vision_json=json.dumps(vision_result, ensure_ascii=False),
            knowledge_refs=knowledge_refs,
        )

        if image_urls:
            raw = self._call_ai_multimodal(
                prompt['system'], prompt['user'], image_urls,
                model=model, default_model='qwen3.6-plus'
            )
        else:
            raw = self._call_ai(
                prompt['system'], prompt['user'], model=model,
                default_model='qwen3.6-plus'
            )
        logger.info(f'[AI RAW] solve_mode_a question={question.id}\n{raw}')
        return self._parse_json_response(raw)

    def solve_mode_b(self, question, image_urls: list, normalized_text: str,
                     vision_result: dict, knowledge_refs: str,
                     model: str = None) -> dict:
        """Step 3b: B 模式求解."""
        prompt = AIPrompts.solve_mode_b(
            normalized_text=normalized_text,
            vision_json=json.dumps(vision_result, ensure_ascii=False),
            knowledge_refs=knowledge_refs,
        )

        if image_urls:
            raw = self._call_ai_multimodal(
                prompt['system'], prompt['user'], image_urls,
                model=model, default_model='qwen3.6-plus'
            )
        else:
            raw = self._call_ai(
                prompt['system'], prompt['user'], model=model,
                default_model='qwen3.6-plus'
            )
        logger.info(f'[AI RAW] solve_mode_b question={question.id}\n{raw}')
        return self._parse_json_response(raw)

    def solve_mode_c(self, question, image_urls: list, normalized_text: str,
                     vision_result: dict, knowledge_refs: str,
                     model: str = None) -> dict:
        """Step 3c: C 模式求解."""
        prompt = AIPrompts.solve_mode_c(
            normalized_text=normalized_text,
            vision_json=json.dumps(vision_result, ensure_ascii=False),
            knowledge_refs=knowledge_refs,
        )

        if image_urls:
            raw = self._call_ai_multimodal(
                prompt['system'], prompt['user'], image_urls,
                model=model, default_model='qwen3.6-plus'
            )
        else:
            raw = self._call_ai(
                prompt['system'], prompt['user'], model=model,
                default_model='qwen3.6-plus'
            )
        logger.info(f'[AI RAW] solve_mode_c question={question.id}\n{raw}')
        return self._parse_json_response(raw)

    def verify_result(self, normalized_text: str, vision_result: dict,
                      solver_output: dict, model: str = None) -> dict:
        """Step 4: 解后校验."""
        prompt = AIPrompts.verify_result(
            normalized_text=normalized_text,
            vision_json=json.dumps(vision_result, ensure_ascii=False),
            solver_output=solver_output,
        )

        raw = self._call_ai(
            prompt['system'], prompt['user'], model=model,
            default_model='qwen3.6-flash'
        )
        return self._parse_json_response(raw)

    def analyze_knowledge_points(self, question, normalized_text: str, subject_hint: str = '',
                                 model: str = None) -> dict:
        """知识点识别：输出 1-5 个知识点 module + 难度（供 save 阶段匹配 knowledge_points 表）."""
        prompt = AIPrompts.analyze_knowledge(normalized_text=normalized_text, subject_hint=subject_hint)
        raw = self._call_ai(prompt['system'], prompt['user'], model=model, default_model='qwen3.6-flash')
        return self._parse_json_response(raw)

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
