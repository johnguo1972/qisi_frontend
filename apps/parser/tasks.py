"""Celery tasks for parser app."""
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from apps.papers.models import ExamPaper, ParseTask
from apps.parser.models import ExamPage, AIParseResult, ExamQuestion
from apps.parser.services.convert_service import word_to_pdf, pdf_to_images
from apps.parser.services.word_preprocess_service import WordPreprocessor
from apps.parser.services.postprocess_service import postprocess_questions
from apps.parser.services.save_service import save_questions
from apps.parser.services.position_service import detect_positions
from apps.parser.services.question_parse_service import parse_questions_stage2
from apps.common import status as const
from apps.common.exceptions import AIRequestError

logger = logging.getLogger(__name__)


def update_task_progress(task, progress: int, current_step: str):
    """Update parse task progress."""
    task.progress = progress
    task.current_step = current_step
    task.save(update_fields=['progress', 'current_step'])


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def parse_paper_task(self, paper_id: int):
    """Main parse task: Word -> PDF -> PNG -> AI -> postprocess -> crop -> save."""
    paper = ExamPaper.objects.get(id=paper_id, is_deleted=False)
    task = ParseTask.objects.filter(paper=paper, status=const.TASK_RUNNING).first()
    if not task:
        task = ParseTask.objects.create(paper=paper, task_type='full_parse', status=const.TASK_RUNNING)

    try:
        task.started_at = timezone.now()
        task.save()

        # Step 1: Word -> PDF (5%)
        update_task_progress(task, 5, '正在转换 Word 为 PDF')
        paper.status = const.PAPER_CONVERTING
        paper.save(update_fields=['status'])

        pdf_dir = settings.MEDIA_ROOT / 'exams' / str(paper.id) / 'pdf'
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_rel = word_to_pdf(str(settings.MEDIA_ROOT / paper.source_file_path), pdf_dir)
        paper.pdf_file_path = pdf_rel
        paper.save(update_fields=['pdf_file_path'])

        # Step 2.5: Word preprocessing (18%)
        update_task_progress(task, 18, '正在提取Word文档结构化信息')
        word_info = None
        try:
            source_path = str(settings.MEDIA_ROOT / paper.source_file_path)
            if source_path.endswith('.docx'):
                preprocessor = WordPreprocessor(source_path)
                word_info = preprocessor.run()
                logger.info(f'Word preprocessing: {len(word_info["question_numbers"])} question numbers, '
                           f'{len(word_info["images"])} images, {len(word_info["image_refs"])} image refs')
            else:
                logger.info(f'Skipping Word preprocessing: source is not .docx')
        except Exception as e:
            logger.warning(f'Word preprocessing failed (non-fatal): {e}')

        # Step 3: PDF -> PNG at 100 DPI for Stage 1 position detection (fast)
        update_task_progress(task, 22, '正在将 PDF 转换为页面图（100 DPI 用于定位）')
        pages_dir_150 = pdf_dir / 'pages_lowdpi'
        pages_dir_150.mkdir(parents=True, exist_ok=True)
        page_images_150 = pdf_to_images(
            str(settings.MEDIA_ROOT / pdf_rel),
            output_dir=str(pages_dir_150),
            dpi=100
        )

        # Stage 1: Question position detection using qwen3.6-plus (150 DPI images)
        update_task_progress(task, 30, '阶段1：题目位置检测（qwen3.6-plus）')
        paper.status = const.PAPER_PARSING
        paper.save(update_fields=['status'])

        page_image_info_150 = [
            {'page_no': pno, 'path': str(settings.MEDIA_ROOT / pi['path'])}
            for pi in page_images_150
            for pno in [pi['page_no']]
        ]

        position_results = detect_positions(page_image_info_150)

        # Save stage 1 results
        total_positioned = sum(len(r.get('questions', [])) for r in position_results)
        logger.info(f'Stage 1 complete: {total_positioned} questions positioned across {len(position_results)} pages')

        # Stage 2: Re-render at 300 DPI for high-quality content parsing
        update_task_progress(task, 45, '正在转换高清页面图（300 DPI 用于解析）')
        pages_dir_300 = pdf_dir / 'pages'
        pages_dir_300.mkdir(parents=True, exist_ok=True)
        page_images_300 = pdf_to_images(
            str(settings.MEDIA_ROOT / pdf_rel),
            output_dir=str(pages_dir_300),
            dpi=300
        )

        # Step 4: Save page records with 300 DPI images (28%)
        update_task_progress(task, 50, '正在保存页面记录')

        # Clean up existing page records (from previous attempts) to avoid duplicate key errors on retry
        ExamPage.objects.filter(paper=paper).delete()
        AIParseResult.objects.filter(paper=paper).delete()

        page_map = {}
        for pi in page_images_300:
            page = ExamPage.objects.create(
                paper=paper, page_no=pi['page_no'], image_path=pi['path'],
                width=pi['width'], height=pi['height'], parse_status=const.PAGE_CONVERTED,
            )
            page_map[page.page_no] = page

        # Save stage 1 position results to AIParseResult for debugging
        for result in position_results:
            page_no = result['page_no']
            page = page_map.get(page_no)
            if page:
                AIParseResult.objects.create(
                    paper=paper, page=page,
                    raw_response=result.get('raw_response', ''),
                    response_json=result.get('raw_response', ''),
                    latency_ms=result.get('latency_ms', 0),
                    is_valid_json=True, model_name='qwen3.6-plus-position',
                )

        paper.total_pages = len(page_images_300)
        paper.status = const.PAPER_PARSING
        paper.save(update_fields=['total_pages', 'status'])

        # Check for existing questions from interrupted runs (resume support)
        existing_questions = list(ExamQuestion.objects.filter(paper=paper).order_by('question_no'))
        existing_question_nos = set(q.question_no for q in existing_questions)

        if existing_question_nos:
            logger.info(f'Resume detected: {len(existing_question_nos)} questions already parsed. '
                        f'Skipping: {sorted(existing_question_nos)}')

        # Filter position_results to skip already-parsed questions
        for result in position_results:
            result['questions'] = [q for q in result.get('questions', [])
                                  if q['question_no'] not in existing_question_nos]

        # Stage 2: Question-level parsing using qwen3-VL-plus
        update_task_progress(task, 50, '阶段2：逐题内容解析（qwen3-VL-plus）')

        # Call stage 2 to parse each question's content using VL model
        def stage2_progress(question_no, current, total):
            pct = 50 + int(30 * current / max(total, 1))
            update_task_progress(task, pct, f'正在解析第 {question_no} 题')

        stage2_results = parse_questions_stage2(position_results, page_map, progress_callback=stage2_progress)

        # Convert stage 2 results (flat list of question dicts) to page-level format
        # that postprocess_questions expects: [{'page_no': int, 'questions': [...]}]
        page_results_map = {}
        for q_parsed in stage2_results:
            pno = q_parsed.get('page_no', 1)
            if pno not in page_results_map:
                page_results_map[pno] = {'page_no': pno, 'questions': []}
            page_results_map[pno]['questions'].append(q_parsed)

        page_results = list(page_results_map.values())
        page_results.sort(key=lambda r: r['page_no'])

        total_parsed = len(stage2_results)
        logger.info(f'Stage 2 complete: {total_parsed} questions parsed')

        # Fallback: if stage 2 produced no results, fall back to stage 1 raw results
        if not page_results:
            logger.warning('Stage 2 produced no results, using stage 1 position data as fallback')
            for result in position_results:
                page_results.append({
                    'page_no': result['page_no'],
                    'questions': result.get('questions', []),
                })

        # Step 6: Postprocessing (82%)
        update_task_progress(task, 82, '正在后处理（合并跨页+校验插图）')
        paper.status = const.PAPER_POSTPROCESSING
        paper.save(update_fields=['status'])
        questions = postprocess_questions(page_results, word_preprocess_result=word_info)

        # Step 7: Cropping (90%)
        update_task_progress(task, 90, '正在裁剪题目插图')
        paper.status = const.PAPER_CROPPING
        paper.save(update_fields=['status'])

        # Step 8: Save to DB (95%)
        update_task_progress(task, 95, '正在保存题目到数据库')
        save_questions(paper, questions, page_map)

        # Done
        update_task_progress(task, 100, '解析完成')
        task.status = const.TASK_SUCCESS
        task.finished_at = timezone.now()
        task.save()
        paper.status = const.PAPER_REVIEWING
        paper.save(update_fields=['status'])
        return {'status': 'success', 'paper_id': paper_id}

    except Exception as e:
        logger.exception(f'Paper {paper_id} parsing failed')
        task.status = const.TASK_FAILED
        task.error_message = str(e)
        task.finished_at = timezone.now()
        task.save()
        paper.status = const.PAPER_FAILED
        paper.error_message = str(e)
        paper.save()
        self.retry(exc=e, countdown=30 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=1, default_retry_delay=15)
def reparse_question_task(self, question_id: int):
    """Re-parse a single question using Stage 2 (qwen3-VL-plus) only."""
    from apps.parser.models import ExamQuestion, QuestionOption, QuestionImage
    from apps.parser.services.question_parse_service import QuestionParseService
    from apps.parser.services.save_service import crop_question_image
    from apps.parser.services.schema_service import validate_and_repair_json
    from apps.review.services.image_recrop_service import recrop_question_image
    import json
    import os

    question = ExamQuestion.objects.select_related('paper').get(id=question_id)
    paper = question.paper

    task = ParseTask.objects.filter(
        question=question, task_type='question_reparse', status=const.TASK_RUNNING
    ).first()

    try:
        # 1. Resolve page images
        page_start = question.page_start or 1
        page_end = question.page_end or page_start
        page_nos = list(range(page_start, page_end + 1))
        pages = ExamPage.objects.filter(paper=paper, page_no__in=page_nos).order_by('page_no')
        if not pages:
            raise Exception(f"No page images found for pages {page_nos}")

        page_image_paths = [str(settings.MEDIA_ROOT / p.image_path) for p in pages if os.path.exists(str(settings.MEDIA_ROOT / p.image_path))]
        if not page_image_paths:
            raise Exception("Page image files not found on disk")

        page_nos_existing = [p.page_no for p in pages if os.path.exists(str(settings.MEDIA_ROOT / p.image_path))]

        # 2. Build question_info
        question_info = {
            'question_no': question.question_no,
            'question_type': question.question_type or 'unknown',
            'section_title': question.section_title or '',
            'page_start': page_start,
            'page_end': page_end,
        }

        # 3. Call Stage 2
        service = QuestionParseService()
        parse_result = service.parse_question(question_info, page_image_paths, page_nos_existing)
        parsed = parse_result['parsed']

        # 4. Postprocess: wrap in page-level format
        parsed['page_no'] = page_start
        parsed['page_end'] = page_end
        page_results = [{'page_no': page_start, 'questions': [parsed]}]
        processed = postprocess_questions(page_results)
        if not processed:
            raise Exception("Postprocessing produced no results")
        q = processed[0]

        # 5. Update ExamQuestion
        question.stem = q.get('stem', '')
        question.stem_html = ''
        question.answer = q.get('answer', '')
        question.analysis = q.get('analysis', '')
        question.solution = q.get('solution', '')
        question.question_type = q.get('question_type', question.question_type)
        question.confidence = q.get('confidence', 0.8)
        question.knowledge_points = q.get('knowledge_points', [])
        question.difficulty = q.get('difficulty', 3)
        question.bbox = q.get('bbox') or question.bbox
        question.raw_explanation = q.get('raw_explanation', '')
        question.page_start = q.get('page_no', page_start)
        question.page_end = q.get('page_end', page_end)
        question.need_review = q.get('need_review', True)
        question.formula_need_review = q.get('formula_need_review', False)
        question.need_review_reason = q.get('need_review_reason', '')
        question.review_status = 'need_review'
        question.parse_status = const.QUESTION_AUTO_PARSED
        question.save()

        # 6. Update options
        QuestionOption.objects.filter(question=question).delete()
        for opt_idx, opt in enumerate(q.get('options', [])):
            QuestionOption.objects.create(
                question=question,
                option_label=opt.get('label', ''),
                content=opt.get('content', ''),
                bbox=opt.get('bbox'),
                sort_order=opt_idx,
            )

        # 7. Re-crop images
        # Delete old AI-cropped images (keep word_extracted)
        QuestionImage.objects.filter(
            question=question
        ).exclude(source_page_image_path__isnull=True).delete()

        # Build page map for cropping
        page_map = {p.page_no: p for p in pages}

        for img_idx, img_info in enumerate(q.get('images', [])):
            bbox = img_info.get('bbox')
            img_page_no = img_info.get('page_no', page_start)
            page = page_map.get(img_page_no)
            if not bbox or not page:
                continue

            src_page_image = str(settings.MEDIA_ROOT / page.image_path)
            crop_dir = settings.MEDIA_ROOT / 'exams' / str(paper.id) / 'crops'
            crop_dir.mkdir(parents=True, exist_ok=True)
            crop_filename = f'q{question.id}_reparse_{img_idx}.png'
            crop_abs_path = str(crop_dir / crop_filename)

            cropped = crop_question_image(src_page_image, bbox, crop_abs_path)
            if cropped:
                rel_path = os.path.relpath(cropped, str(settings.MEDIA_ROOT))
                QuestionImage.objects.create(
                    paper=paper,
                    question=question,
                    page=page,
                    image_type=img_info.get('image_type', 'diagram'),
                    file_path=rel_path,
                    source_page_image_path=page.image_path,
                    bbox=bbox,
                    description=img_info.get('description', 'AI重裁'),
                    sort_order=img_idx,
                )

        # 8. Save AIParseResult for audit
        AIParseResult.objects.create(
            paper=paper,
            raw_response=parse_result.get('raw_response', ''),
            response_json=parse_result.get('response_json', ''),
            latency_ms=parse_result.get('latency_ms', 0),
            is_valid_json=True,
            model_name='qwen3-vl-plus-reparse',
        )

        # 9. Update task status
        if task:
            task.status = const.TASK_SUCCESS
            task.progress = 100
            task.current_step = '解析完成'
            task.finished_at = timezone.now()
            task.save()

        logger.info(f'Single question re-parse complete: question_id={question_id}')
        return {'status': 'success', 'question_id': question_id}

    except Exception as e:
        logger.exception(f'Question {question_id} re-parse failed')
        if task:
            task.status = const.TASK_FAILED
            task.error_message = str(e)
            task.finished_at = timezone.now()
            task.save()
        self.retry(exc=e, countdown=15 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=1, default_retry_delay=15)
def reparse_page_task(self, paper_id: int, page_no: int):
    """Re-parse a single page: delete questions for that page, re-run Stage 1 + Stage 2."""
    from apps.parser.models import QuestionOption, QuestionImage

    paper = ExamPaper.objects.get(id=paper_id, is_deleted=False)
    task = ParseTask.objects.create(
        paper=paper, task_type='page_reparse', status=const.TASK_RUNNING,
        progress=0, current_step=f'正在重解析第 {page_no} 页'
    )

    try:
        # 1. Delete existing questions for this page
        page_questions = ExamQuestion.objects.filter(paper=paper, page_start=page_no)
        q_ids = list(page_questions.values_list('id', flat=True))
        QuestionOption.objects.filter(question_id__in=q_ids).delete()
        QuestionImage.objects.filter(question_id__in=q_ids).delete()
        page_questions.delete()

        # 2. Re-run Stage 1 (position detection) for this page only
        update_task_progress(task, 10, f'正在重检测第 {page_no} 页题目位置')
        page = ExamPage.objects.get(paper=paper, page_no=page_no)
        page_image_info = [{'page_no': page_no, 'path': str(settings.MEDIA_ROOT / page.image_path)}]
        position_results = detect_positions(page_image_info)

        # 3. Re-run Stage 2 (question parsing)
        update_task_progress(task, 30, f'正在重解析第 {page_no} 页题目内容')
        stage2_results = parse_questions_stage2(
            position_results, {page_no: page},
            progress_callback=lambda q, c, t:
                update_task_progress(task, 30 + int(50 * c / max(t, 1)),
                                    f'正在解析第 {q} 题')
        )

        # 4. Postprocess + save
        update_task_progress(task, 85, '正在后处理')
        page_results = [{'page_no': page_no, 'questions': stage2_results}]
        questions = postprocess_questions(page_results)

        update_task_progress(task, 95, '正在保存')
        save_questions(paper, questions, {page_no: page})

        update_task_progress(task, 100, '重解析完成')
        task.status = const.TASK_SUCCESS
        task.finished_at = timezone.now()
        task.save()
        return {'status': 'success', 'paper_id': paper_id, 'page_no': page_no}

    except Exception as e:
        logger.exception(f'Page {page_no} re-parse failed for paper {paper_id}')
        task.status = const.TASK_FAILED
        task.error_message = str(e)
        task.finished_at = timezone.now()
        task.save()
        self.retry(exc=e, countdown=15 * (2 ** self.request.retries))


@shared_task
def periodic_stale_task_check():
    """Celery Beat task: detect and retry stale parse tasks every 5 minutes."""
    from datetime import timedelta

    stale_threshold = timezone.now() - timedelta(minutes=15)
    stale_tasks = ParseTask.objects.filter(
        status=const.TASK_RUNNING,
        started_at__isnull=False,
        started_at__lt=stale_threshold,
        paper__isnull=False  # only check paper-level tasks
    )

    count = 0
    for task in stale_tasks:
        logger.warning(f'Detected stale task {task.id} (started {task.started_at}), marking as failed')
        task.status = const.TASK_FAILED
        task.error_message = 'Task stalled (auto-detected)'
        task.finished_at = timezone.now()
        task.save()

        paper = task.paper
        if paper:
            paper.status = const.PAPER_FAILED
            paper.error_message = '解析任务超时（自动检测）'
            paper.save()
        count += 1

    if count:
        logger.info(f'Processed {count} stale tasks')
    return {'checked': stale_tasks.count(), 'failed': count}
