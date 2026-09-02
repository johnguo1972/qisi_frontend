"""HTMX page routes for review app."""
import logging
from django.urls import path
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, ExamPage, QuestionImage
from apps.review.services.image_recrop_service import recrop_question_image, delete_question_image
from django.http import HttpResponse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def paper_list_htmx(request):
    papers = ExamPaper.objects.filter(is_deleted=False).order_by('-created_at')
    return render(request, 'papers/list.html', {'papers': papers})


def paper_detail_htmx(request, paper_id):
    paper = get_object_or_404(ExamPaper, id=paper_id, is_deleted=False)
    return render(request, 'papers/detail.html', {
        'paper': paper,
        'pages': ExamPage.objects.filter(paper=paper).order_by('page_no'),
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


urlpatterns = [
    path('', paper_list_htmx, name='paper-list-htmx'),
    path('papers/<uuid:paper_id>/', paper_detail_htmx, name='paper-detail-htmx'),
    path('papers/<uuid:paper_id>/edit-inline/', paper_edit_inline_htmx, name='paper-edit-inline-htmx'),
    path('papers/<uuid:paper_id>/delete-htmx/', paper_delete_htmx, name='paper-delete-htmx'),
    path('review/<uuid:paper_id>/', review_list_htmx, name='review-list-htmx'),
    path('review/question/<uuid:question_id>/', question_edit_htmx, name='question-edit-htmx'),
    path('review/question/<uuid:question_id>/preview/', question_preview_fragment_htmx, name='question-preview-htmx'),
    path('review/question/<uuid:question_id>/images/panel/', image_correction_panel_htmx, name='image-correction-panel-htmx'),
    path('review/question/<uuid:question_id>/images/recrop/', image_recrop_htmx, name='image-recrop-htmx'),
    path('review/question/<uuid:question_id>/images/<uuid:image_id>/delete/', image_delete_htmx, name='image-delete-htmx'),
]
