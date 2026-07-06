"""HTMX routes for knowledge app."""
import logging
from django.urls import path
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.http import HttpResponse
from django.shortcuts import render
from apps.knowledge.models import KnowledgePoint

logger = logging.getLogger(__name__)


@require_GET
def chapter_points(request, chapter_name):
    """Return the points table HTML for a given chapter."""
    subject = request.GET.get('subject', 'math')
    stage = request.GET.get('stage', 'primary')
    grade_index = request.GET.get('grade_index', '1')
    term = request.GET.get('term', 'up')

    points = KnowledgePoint.objects.filter(
        subject=subject,
        stage=stage,
        grade_index=int(grade_index),
        term=term,
        chapter=chapter_name,
    ).order_by('module', 'node_type')

    return render(request, 'knowledge/fragments/chapter_points.html', {
        'chapter_name': chapter_name,
        'points': points,
        'context': {
            'subject': subject,
            'stage': stage,
            'grade_index': int(grade_index),
            'term': term,
        },
    })


@require_GET
def point_form_new(request):
    """Return the form HTML for creating a new knowledge point."""
    return render(request, 'knowledge/fragments/point_form.html', {
        'subject': request.GET.get('subject', 'math'),
        'stage': request.GET.get('stage', 'primary'),
        'grade_index': int(request.GET.get('grade_index', 1)),
        'term': request.GET.get('term', 'up'),
        'chapter': request.GET.get('chapter', ''),
        'module': request.GET.get('module', ''),
        'node_type': request.GET.get('node_type', 'formula'),
        'content': '',
        'point': None,
        'action': 'new',
    })


@require_GET
def point_form_edit(request, point_id):
    """Return the form HTML for editing an existing knowledge point."""
    point = get_object_or_404(KnowledgePoint, id=point_id)
    return render(request, 'knowledge/fragments/point_form.html', {
        'point': point,
        'subject': point.subject,
        'stage': point.stage,
        'grade_index': point.grade_index,
        'term': point.term,
        'chapter': point.chapter,
        'module': point.module,
        'node_type': point.node_type,
        'content': point.content,
        'action': 'edit',
    })


@require_POST
@csrf_exempt
def point_create(request):
    """Create a new knowledge point."""
    try:
        grade_index = int(request.POST.get('grade_index', 1))
        grade_name = KnowledgePoint.GRADE_LABELS.get(grade_index, '')
        point = KnowledgePoint.objects.create(
            subject=request.POST.get('subject', 'math'),
            stage=request.POST.get('stage', 'primary'),
            grade_index=grade_index,
            grade_name=grade_name,
            term=request.POST.get('term', 'up'),
            chapter=request.POST.get('chapter', '').strip(),
            module=request.POST.get('module', '').strip(),
            node_type=request.POST.get('node_type', 'formula'),
            content=request.POST.get('content', '').strip(),
        )
        url = (
            f'/knowledge/chapter/{point.chapter}/'
            f'?subject={point.subject}&stage={point.stage}'
            f'&grade_index={point.grade_index}&term={point.term}'
        )
        return HttpResponse(
            f"<script>htmx.ajax('GET', '{url}', '#kp-table');</script>"
        )
    except Exception as e:
        logger.error(f'Failed to create knowledge point: {e}', exc_info=True)
        return HttpResponse(f'<div class="alert alert-danger">保存失败: {e}</div>')


@require_POST
@csrf_exempt
def point_update(request, point_id):
    """Update an existing knowledge point."""
    try:
        point = KnowledgePoint.objects.get(id=point_id)
        point.chapter = request.POST.get('chapter', '').strip()
        point.module = request.POST.get('module', '').strip()
        point.node_type = request.POST.get('node_type', 'formula')
        point.content = request.POST.get('content', '').strip()
        point.save()

        url = (
            f'/knowledge/chapter/{point.chapter}/'
            f'?subject={point.subject}&stage={point.stage}'
            f'&grade_index={point.grade_index}&term={point.term}'
        )
        return HttpResponse(
            f"<script>htmx.ajax('GET', '{url}', '#kp-table');</script>"
        )
    except KnowledgePoint.DoesNotExist:
        return HttpResponse(
            '<div class="alert alert-danger">知识点不存在</div>', status=404
        )
    except Exception as e:
        logger.error(f'Failed to update knowledge point: {e}', exc_info=True)
        return HttpResponse(f'<div class="alert alert-danger">保存失败: {e}</div>')


@require_POST
@csrf_exempt
def point_delete(request, point_id):
    """Delete a knowledge point."""
    try:
        point = KnowledgePoint.objects.get(id=point_id)
        chapter = point.chapter
        subject = point.subject
        stage = point.stage
        grade_index = point.grade_index
        term = point.term
        point.delete()

        url = (
            f'/knowledge/chapter/{chapter}/'
            f'?subject={subject}&stage={stage}'
            f'&grade_index={grade_index}&term={term}'
        )
        return HttpResponse(
            f"<script>htmx.ajax('GET', '{url}', '#kp-table');</script>"
        )
    except KnowledgePoint.DoesNotExist:
        return HttpResponse(
            '<div class="alert alert-danger">知识点不存在</div>', status=404
        )
    except Exception as e:
        logger.error(f'Failed to delete knowledge point: {e}', exc_info=True)
        return HttpResponse(f'<div class="alert alert-danger">删除失败: {e}</div>')


urlpatterns = [
    path('knowledge/chapter/<str:chapter_name>/', chapter_points, name='knowledge-chapter-points'),
    path('knowledge/point/new/', point_form_new, name='knowledge-point-form-new'),
    path('knowledge/point/<int:point_id>/edit/', point_form_edit, name='knowledge-point-form-edit'),
    path('knowledge/point/new/submit/', point_create, name='knowledge-point-create'),
    path('knowledge/point/<int:point_id>/update/', point_update, name='knowledge-point-update'),
    path('knowledge/point/<int:point_id>/delete/', point_delete, name='knowledge-point-delete'),
]
