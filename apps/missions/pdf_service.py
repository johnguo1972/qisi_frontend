"""Generate and locate the published worksheet PDF for a learning mission."""

import os
import re
from pathlib import Path

from django.conf import settings

from apps.missions.models import MissionQuestionRel
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption
from .services import ordered_mission_question_rels


def _mission_questions(mission):
    """Build PDF input in the exact MissionQuestionRel sort order."""
    relations = list(
        ordered_mission_question_rels(mission)
    )
    question_ids = [relation.question_id for relation in relations]
    question_map = {
        str(question['id']): question
        for question in ExamQuestion.objects.filter(id__in=question_ids).values(
            'id', 'question_no', 'question_type', 'stem', 'stem_html',
            'answer', 'analysis', 'knowledge_points',
        )
    }

    questions = []
    for relation in relations:
        question = question_map.get(str(relation.question_id))
        if not question:
            continue
        options = QuestionOption.objects.filter(
            question_id=question['id'],
        ).values('option_label', 'content').order_by('sort_order')
        images = QuestionImage.objects.filter(
            question_id=question['id'],
        ).exclude(image_type='formula').values(
            'file_path', 'placement', 'sort_order', 'display_width'
        ).order_by('sort_order')
        snapshot = relation.question_snapshot or {}
        snapshot_options = snapshot.get('options_html') if snapshot else None
        snapshot_images = snapshot.get('image_items') if snapshot else None
        questions.append({
            **question,
            **snapshot,
            'id': question['id'],
            '_pdf_title': mission.mission_name,
            'options_html': snapshot_options if snapshot_options is not None else [
                {'label': option['option_label'], 'content': option['content']}
                for option in options
            ],
            'image_urls': [
                item.get('file_path', '') if isinstance(item, dict) else item['file_path']
                for item in (snapshot_images if snapshot_images is not None else images)
            ],
            'image_items': snapshot_images if snapshot_images is not None else list(images),
        })
    return questions


def mission_pdf_relative_path(mission):
    title = re.sub(r'[\\/:*?"<>|]+', '_', str(mission.mission_name or '')).strip(' ._')[:60]
    title = title or 'mission'
    return f'exports/{title}_mission_{mission.id}.pdf'


def mission_pdf_download_url(mission):
    if not mission.pdf_file_path:
        return ''
    return f"{settings.MEDIA_URL.rstrip('/')}/{mission.pdf_file_path.lstrip('/')}"


def generate_mission_pdf(mission):
    """Generate or replace the mission worksheet and return its media path."""
    questions = _mission_questions(mission)

    # Imported lazily to avoid importing the student view during URL loading.
    from apps.study.student_views import _build_pdf

    relative_path = mission_pdf_relative_path(mission)
    output_path = Path(settings.MEDIA_ROOT) / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_build_pdf('mission', questions, False, ''))

    if mission.pdf_file_path != relative_path:
        mission.pdf_file_path = relative_path
        mission.save(update_fields=['pdf_file_path', 'updated_at'])
    return relative_path


def ensure_mission_pdf(mission):
    """Return the stored path, generating it only for legacy missions."""
    if mission.pdf_file_path:
        output_path = Path(settings.MEDIA_ROOT) / mission.pdf_file_path
        if output_path.exists():
            return mission.pdf_file_path
    return generate_mission_pdf(mission)
