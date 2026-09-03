"""Read helpers for immutable class-mission question snapshots."""
import copy

from apps.common.media import media_url
from .models import MissionQuestionRel
from .services import ordered_mission_question_rels


def mission_question_relation(mission_id, question_id, level_id=None):
    mission_relations = ordered_mission_question_rels(mission_id)
    relations = [relation for relation in mission_relations if str(relation.question_id) == str(question_id)]
    if level_id:
        relations = [relation for relation in relations if str(relation.level_id) == str(level_id)]
    return relations[0] if relations else None


def apply_snapshot_to_question(question, relation):
    """Return a question-like object using the publication snapshot fields."""
    snapshot = (relation.question_snapshot or {}) if relation else {}
    if not snapshot:
        return question
    result = copy.copy(question)
    for field in (
        'question_no', 'question_type', 'stem', 'stem_html', 'answer',
        'analysis', 'solution', 'material', 'subquestions', 'tables',
        'difficulty', 'knowledge_points', 'ai_answer_a',
    ):
        if field in snapshot:
            setattr(result, field, snapshot[field])
    return result


def snapshot_payload(question, relation):
    """Build the student-facing payload from the immutable relation snapshot."""
    snapshot = (relation.question_snapshot or {}) if relation else {}
    payload = {
        'id': question.id,
        'question_no': question.question_no,
        'question_type': question.question_type,
        'difficulty': float(question.difficulty) if question.difficulty else None,
        'stem': question.stem or '',
        'stem_html': question.stem_html or '',
        'answer': question.answer or '',
        'analysis': question.analysis or '',
        'solution': question.solution or '',
        'subquestions': question.subquestions or [],
        'tables': question.tables or [],
        'images': [],
        'options': [],
    }
    source_images = [
        {
            'id': img.id, 'file_path': img.file_path,
            'url': media_url(img.file_path),
            'image_type': img.image_type, 'placement': img.placement,
            'sort_order': img.sort_order, 'display_width': img.display_width,
            'description': img.description or '',
        }
        for img in question.images.all().order_by('sort_order')
        if img.file_path and img.image_type != 'formula'
    ]
    source_options = []
    for option in question.options.all().order_by('sort_order', 'id'):
        item = {'label': option.option_label, 'content': option.content}
        if option.content_html:
            item['content_html'] = option.content_html
        source_options.append(item)
    if not snapshot:
        payload['images'] = source_images
        payload['options'] = source_options
        return payload
    for field in (
        'question_no', 'question_type', 'stem', 'stem_html', 'answer',
        'analysis', 'solution', 'subquestions', 'tables', 'difficulty',
    ):
        if field in snapshot:
            payload[field] = snapshot[field]
    # Older publication snapshots do not carry all structural fields.  Keep
    # their published scalar values, but use the source relation data only for
    # fields that were never captured.  An explicit [] remains an immutable
    # published empty value.
    if 'options_html' in snapshot:
        payload['options'] = []
        for item in (snapshot.get('options_html') or []):
            if not isinstance(item, dict):
                continue
            option = {
                'label': item.get('label') or item.get('option_label', ''),
                'content': item.get('content', ''),
            }
            if item.get('content_html'):
                option['content_html'] = item['content_html']
            payload['options'].append(option)
    else:
        payload['options'] = source_options
    if 'image_items' in snapshot:
        payload['images'] = [
            {
                'id': item.get('id'), 'file_path': item.get('file_path', ''),
                'url': item.get('url', ''), 'image_type': item.get('image_type', 'other'),
                'placement': item.get('placement', 'stem'), 'sort_order': item.get('sort_order', 0),
                'display_width': item.get('display_width'), 'description': item.get('description', ''),
            }
            for item in (snapshot.get('image_items') or [])
            if isinstance(item, dict) and (item.get('file_path') or item.get('url'))
        ]
    else:
        payload['images'] = source_images
    return payload
