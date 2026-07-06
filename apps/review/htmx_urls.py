"""HTMX page routes for review app."""
import logging
from django.urls import path
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from apps.papers.models import ExamPaper, ParseTask
from apps.parser.models import ExamQuestion, ExamPage, AIParseResult, QuestionImage
from apps.parser.tasks import parse_paper_task
from apps.review.services.image_recrop_service import recrop_question_image, delete_question_image
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
import os
from django.conf import settings
from apps.common import status as const
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)


def upload_modal_htmx(request):
    """Return the upload modal HTML."""
    return render(request, 'papers/upload_modal.html')


def paper_list_htmx(request):
    papers = ExamPaper.objects.filter(is_deleted=False).order_by('-created_at')
    return render(request, 'papers/list.html', {'papers': papers})


@csrf_exempt
def upload_paper_htmx(request):
    """Handle paper upload via HTMX form submission."""
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            return HttpResponse('<div class="alert alert-danger">请选择文件</div>')

        title = (request.POST.get('title') or '').strip()
        if not title:
            title = file.name.replace('.docx', '')
        subject = request.POST.get('subject', '数学')
        stage = request.POST.get('stage', '')
        grade = request.POST.get('grade', '')
        region = (request.POST.get('region') or '').strip()

        # Save file to media directory
        import uuid
        paper_id = str(uuid.uuid4())[:8]
        import os
        from django.conf import settings
        paper_dir = os.path.join(settings.MEDIA_ROOT, 'exams', paper_id, 'source')
        os.makedirs(paper_dir, exist_ok=True)
        file_path = os.path.join(paper_dir, file.name)
        with open(file_path, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        paper = ExamPaper.objects.create(
            title=title,
            subject=subject,
            stage=stage,
            grade=grade,
            region=region,
            source_file_path=os.path.relpath(file_path, settings.MEDIA_ROOT),
            status=const.PAPER_UPLOADED,
        )

        task = ParseTask.objects.create(
            paper=paper,
            task_type='full_parse',
            status=const.TASK_RUNNING,
        )

        # Dispatch Celery task
        parse_paper_task.delay(paper.id)

        return render(request, 'papers/upload_success.html', {
            'paper': paper, 'task': task
        })

    return HttpResponse('', status=405)


def paper_detail_htmx(request, paper_id):
    paper = get_object_or_404(ExamPaper, id=paper_id, is_deleted=False)
    parse_task = ParseTask.objects.filter(paper=paper).order_by('-created_at').first()
    pages = ExamPage.objects.filter(paper=paper).order_by('page_no')
    return render(request, 'papers/detail.html', {
        'paper': paper, 'parse_task': parse_task, 'pages': pages
    })


def paper_progress_htmx(request, paper_id):
    """Return only the progress card HTML fragment for polling."""
    paper = get_object_or_404(ExamPaper, id=paper_id, is_deleted=False)
    parse_task = ParseTask.objects.filter(paper=paper).order_by('-created_at').first()
    pages = ExamPage.objects.filter(paper=paper).order_by('page_no')
    return render(request, 'papers/progress_fragment.html', {
        'paper': paper, 'parse_task': parse_task, 'pages': pages
    })


def review_list_htmx(request, paper_id):
    paper = get_object_or_404(ExamPaper, id=paper_id, is_deleted=False)
    questions = ExamQuestion.objects.filter(paper=paper).order_by('sort_order')
    return render(request, 'review/list.html', {
        'paper': paper, 'questions': questions
    })


def question_edit_htmx(request, question_id):
    question = get_object_or_404(ExamQuestion.objects.prefetch_related('images', 'options'), id=question_id)
    pages = ExamPage.objects.filter(
        paper=question.paper,
        page_no__gte=question.page_start,
        page_no__lte=question.page_end or question.page_start
    ).order_by('page_no')

    prev_q = ExamQuestion.objects.filter(
        paper=question.paper, sort_order__lt=question.sort_order
    ).order_by('-sort_order').first()
    next_q = ExamQuestion.objects.filter(
        paper=question.paper, sort_order__gt=question.sort_order
    ).order_by('sort_order').first()

    total_qs = ExamQuestion.objects.filter(paper=question.paper).count()
    question_index = ExamQuestion.objects.filter(
        paper=question.paper, sort_order__lte=question.sort_order
    ).count()

    return render(request, 'review/question_edit.html', {
        'question': question, 'paper': question.paper,
        'images': list(question.images.all()),
        'pages': pages,
        'prev_question': prev_q,
        'next_question': next_q,
        'total_questions': total_qs,
        'question_index': question_index,
    })


def question_preview_fragment_htmx(request, question_id):
    """Return just the preview section HTML for HTMX swap."""
    question = get_object_or_404(
        ExamQuestion.objects.prefetch_related('images', 'options'), id=question_id
    )
    return render(request, 'review/fragments/question_preview.html', {
        'question': question,
        'images': list(question.images.all()),
    })


def paper_edit_inline_htmx(request, paper_id):
    """Inline edit for paper_code and region on the paper list row."""
    paper = get_object_or_404(ExamPaper, id=paper_id, is_deleted=False)

    if request.method == 'POST':
        new_code = request.POST.get('paper_code', '').strip()
        new_region = request.POST.get('region', '').strip()

        # Validate uniqueness of paper_code
        if new_code and new_code != paper.paper_code:
            if ExamPaper.objects.filter(paper_code=new_code, is_deleted=False).exclude(id=paper_id).exists():
                return HttpResponse(
                    '<tr><td colspan="9" class="text-danger">试卷编号已存在</td></tr>',
                    status=409,
                )
            paper.paper_code = new_code

        paper.region = new_region or ''
        paper.save(update_fields=['paper_code', 'region'])
        return render(request, 'papers/fragments/paper_row_readonly.html', {'paper': paper})

    # GET: return editable form
    return render(request, 'papers/fragments/paper_row_edit.html', {'paper': paper})


@require_POST
def paper_reparse_htmx(request, paper_id):
    """Reset a failed paper, clean old parse data, and re-dispatch parsing."""
    paper = get_object_or_404(ExamPaper, id=paper_id, is_deleted=False)

    # Clean up existing parse results to avoid duplicate key conflicts
    ExamQuestion.objects.filter(paper=paper).delete()
    AIParseResult.objects.filter(paper=paper).delete()
    ExamPage.objects.filter(paper=paper).delete()

    paper.status = const.PAPER_PARSING
    paper.error_message = ''
    paper.save(update_fields=['status', 'error_message'])

    # Create a new parse task
    task = ParseTask.objects.create(
        paper=paper,
        task_type='full_parse',
        status=const.TASK_RUNNING,
    )

    parse_paper_task.delay(paper.id)

    # Check if this is a list page request (has hx-current-url header) or detail page
    if 'HX-Current-URL' in request.headers:
        return render(request, 'papers/fragments/paper_row_readonly.html', {'paper': paper})

    # Detail page: return progress card
    return render(request, 'papers/fragments/progress_restarted.html', {
        'paper': paper, 'task': task
    })


@require_POST
def paper_delete_htmx(request, paper_id):
    """Soft-delete a paper by setting is_deleted=True."""
    paper = get_object_or_404(ExamPaper, id=paper_id, is_deleted=False)
    paper.is_deleted = True
    paper.save(update_fields=['is_deleted'])
    return HttpResponse('')


# ===== Image correction endpoints =====

def image_correction_panel_htmx(request, question_id):
    """Return the image correction panel HTML fragment."""
    question = get_object_or_404(
        ExamQuestion.objects.prefetch_related('images'), id=question_id
    )
    # Load ALL page images for this paper (not just page_start~page_end)
    # so user can switch to any page to find diagrams
    pages = ExamPage.objects.filter(
        paper=question.paper
    ).order_by('page_no')
    images = list(question.images.all().order_by('sort_order'))

    # Default to page_start, but allow viewing all pages
    default_page_no = question.page_start or 1

    return render(request, 'review/fragments/image_correction.html', {
        'question': question,
        'pages': pages,
        'images': images,
        'default_page_no': default_page_no,
    })


@require_POST
@csrf_exempt
def image_recrop_htmx(request, question_id):
    """Re-crop an image with a new bbox, or add a new image."""
    question = get_object_or_404(ExamQuestion, id=question_id)

    try:
        x1 = int(request.POST.get('x1', 0))
        y1 = int(request.POST.get('y1', 0))
        x2 = int(request.POST.get('x2', 0))
        y2 = int(request.POST.get('y2', 0))
        image_id = request.POST.get('image_id', '').strip() or None
        page_no = request.POST.get('page_no', '')
        page_no = int(page_no) if page_no else None
        description = (request.POST.get('description', '') or '人工重裁').strip()

        logger.info(f'Recrop request: question={question_id}, bbox=[{x1},{y1},{x2},{y2}], page_no={page_no}, image_id={image_id}')

        # Validate bbox
        if x2 <= x1 or y2 <= y1:
            return render(request, 'review/fragments/image_crop_error.html', {
                'error': '坐标无效：x2 必须大于 x1，y2 必须大于 y1'
            })

        if image_id:
            img = recrop_question_image(question, [x1, y1, x2, y2], image_id=int(image_id),
                                        page_no=page_no, description=description)
        else:
            img = recrop_question_image(question, [x1, y1, x2, y2], page_no=page_no,
                                        description=description)

        # Return updated image list
        pages = ExamPage.objects.filter(
            paper=question.paper
        ).order_by('page_no')
        images = list(QuestionImage.objects.filter(question=question).order_by('sort_order'))

        return render(request, 'review/fragments/image_correction.html', {
            'question': question,
            'pages': pages,
            'images': images,
            'default_page_no': question.page_start or 1,
            'success': '图片已更新',
        })
    except Exception as e:
        logger.error(f'Recrop failed: {e}', exc_info=True)
        return render(request, 'review/fragments/image_crop_error.html', {
            'error': str(e)
        })


@require_POST
@csrf_exempt
def image_delete_htmx(request, question_id, image_id):
    """Delete a question image."""
    question = get_object_or_404(ExamQuestion, id=question_id)
    try:
        img = QuestionImage.objects.get(id=image_id, question=question)
        delete_question_image(img)
    except QuestionImage.DoesNotExist:
        pass

    # Return updated image list
    pages = ExamPage.objects.filter(
        paper=question.paper
    ).order_by('page_no')
    images = list(QuestionImage.objects.filter(question=question).order_by('sort_order'))

    return render(request, 'review/fragments/image_correction.html', {
        'question': question,
        'pages': pages,
        'images': images,
        'default_page_no': question.page_start or 1,
        'success': '图片已删除',
    })


def question_reparse_htmx(request, question_id):
    """Trigger a single-question re-parse via Celery."""
    from apps.parser.models import ExamQuestion
    from apps.parser.tasks import reparse_question_task

    question = get_object_or_404(ExamQuestion.objects.select_related('paper'), id=question_id)

    # Save page range from form if provided (user may have edited before clicking reparse)
    new_page_start = request.POST.get('page_start', '').strip()
    new_page_end = request.POST.get('page_end', '').strip()
    if new_page_start:
        question.page_start = int(new_page_start)
    if new_page_end:
        question.page_end = int(new_page_end) if new_page_end else None
    question.save(update_fields=['page_start', 'page_end'])

    # Check if already running
    existing_task = ParseTask.objects.filter(
        question=question, task_type='question_reparse',
        status__in=[const.TASK_PENDING, const.TASK_RUNNING]
    ).first()
    if existing_task:
        return render(request, 'review/fragments/question_reparse_progress.html', {
            'question': question, 'task': existing_task, 'paper': question.paper,
        })

    # Create new task record
    task = ParseTask.objects.create(
        paper=question.paper,
        question=question,
        task_type='question_reparse',
        status=const.TASK_RUNNING,
        progress=0,
        current_step='正在启动 AI 解析',
    )

    # Dispatch Celery task
    reparse_question_task.delay(question_id)

    return render(request, 'review/fragments/question_reparse_progress.html', {
        'question': question, 'task': task, 'paper': question.paper,
    })


def question_reparse_progress_htmx(request, question_id):
    """Poll for single-question re-parse progress."""
    from apps.parser.models import ExamQuestion

    question = get_object_or_404(ExamQuestion.objects.select_related('paper'), id=question_id)
    task = ParseTask.objects.filter(
        question=question, task_type='question_reparse'
    ).order_by('-created_at').first()

    return render(request, 'review/fragments/question_reparse_progress.html', {
        'question': question, 'task': task, 'paper': question.paper,
    })


urlpatterns = [
    path('', paper_list_htmx, name='paper-list-htmx'),
    path('upload-modal/', upload_modal_htmx, name='upload-modal-htmx'),
    path('papers/upload/', upload_paper_htmx, name='upload-paper-htmx'),
    path('papers/<int:paper_id>/', paper_detail_htmx, name='paper-detail-htmx'),
    path('papers/<int:paper_id>/progress/', paper_progress_htmx, name='paper-progress-htmx'),
    path('papers/<int:paper_id>/edit-inline/', paper_edit_inline_htmx, name='paper-edit-inline-htmx'),
    path('papers/<int:paper_id>/reparse-htmx/', paper_reparse_htmx, name='paper-reparse-htmx'),
    path('papers/<int:paper_id>/delete-htmx/', paper_delete_htmx, name='paper-delete-htmx'),
    path('review/<int:paper_id>/', review_list_htmx, name='review-list-htmx'),
    path('review/question/<int:question_id>/', question_edit_htmx, name='question-edit-htmx'),
    path('review/question/<int:question_id>/preview/', question_preview_fragment_htmx, name='question-preview-htmx'),
    path('review/question/<int:question_id>/images/panel/', image_correction_panel_htmx, name='image-correction-panel-htmx'),
    path('review/question/<int:question_id>/images/recrop/', image_recrop_htmx, name='image-recrop-htmx'),
    path('review/question/<int:question_id>/images/<int:image_id>/delete/', image_delete_htmx, name='image-delete-htmx'),
    path('review/question/<int:question_id>/reparse-htmx/', question_reparse_htmx, name='question-reparse-htmx'),
    path('review/question/<int:question_id>/reparse-progress/', question_reparse_progress_htmx, name='question-reparse-progress-htmx'),
]
