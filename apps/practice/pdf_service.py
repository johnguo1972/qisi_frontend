"""PDF generation for persisted personal practice sets."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from django.conf import settings
from apps.common.media import media_url
from apps.parser.models import ExamQuestion

from .models import PracticeSet


def _pdf_question_from_snapshot(snapshot, question=None, *, include_answers=False):
    data = deepcopy(snapshot or {})
    data['options_html'] = [
        {'label': item.get('label', ''), 'content': item.get('content', '')}
        for item in (data.get('options') or [])
        if isinstance(item, dict)
    ]
    data['image_urls'] = [
        item.get('file_path') or item.get('url')
        for item in (data.get('images') or [])
        if isinstance(item, dict) and (item.get('file_path') or item.get('url'))
    ]
    data['image_items'] = [
        {
            'file_path': item.get('file_path') or item.get('url'),
            'placement': item.get('placement') or 'stem',
            'sort_order': item.get('sort_order', 0),
            'display_width': item.get('display_width'),
        }
        for item in (data.get('images') or [])
        if isinstance(item, dict) and (item.get('file_path') or item.get('url'))
    ]
    if include_answers and question is not None:
        data['answer'] = question.answer or ''
        data['analysis'] = question.analysis or ''
    else:
        data.pop('answer', None)
        data.pop('analysis', None)
    return data


def practice_pdf_questions(practice_set, *, include_answers=False):
    """Build PDF input in persisted ``sort_no`` order."""
    items = list(practice_set.items.all().order_by('sort_no', 'id'))
    question_ids = [item.question_id for item in items]
    question_map = {
        str(question.id): question
        for question in ExamQuestion.objects.filter(id__in=question_ids)
    }
    questions = [
        _pdf_question_from_snapshot(
            item.display_snapshot,
            question_map.get(str(item.question_id)),
            include_answers=include_answers,
        )
        for item in items
    ]
    if questions:
        questions[0]['_pdf_title'] = practice_set.title
    return questions


def practice_pdf_relative_path(practice_set, *, include_answers=False):
    suffix = '_answers' if include_answers else ''
    title = re.sub(r'[\\/:*?"<>|]+', '_', str(practice_set.title or '')).strip(' ._')[:60]
    title = title or 'practice'
    return f'exports/{title}_practice_{practice_set.id}_v{practice_set.pdf_version}{suffix}.pdf'


def practice_pdf_download_url(relative_path):
    return media_url(relative_path) if relative_path else ''


def generate_practice_pdf(practice_set, *, include_answers=False, watermark_text=''):
    questions = practice_pdf_questions(practice_set, include_answers=include_answers)
    if not questions:
        raise ValueError('精练作业没有题目')
    from apps.study.student_views import _build_pdf

    relative_path = practice_pdf_relative_path(practice_set, include_answers=include_answers)
    output_path = Path(settings.MEDIA_ROOT) / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_build_pdf('practice', questions, include_answers, watermark_text))
    # The model's canonical PDF is always the answer-free worksheet. An answer
    # sheet is separately named and returned to the authorized student only;
    # it must never become the path exposed by the ordinary GET endpoint.
    if not include_answers and practice_set.pdf_file_path != relative_path:
        practice_set.pdf_file_path = relative_path
        practice_set.save(update_fields=['pdf_file_path', 'updated_at'])
    return relative_path


def ensure_practice_pdf(practice_set):
    if practice_set.pdf_file_path:
        output_path = Path(settings.MEDIA_ROOT) / practice_set.pdf_file_path
        if output_path.exists():
            return practice_set.pdf_file_path
    return generate_practice_pdf(practice_set)
