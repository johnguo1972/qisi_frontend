"""Strict candidate recommendation for the wrong-book practice flow.

This module is deliberately independent from ``apps.wrongbook.services``.
The latter serves the legacy ``/variants/`` flow and must retain its behavior.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

from apps.common.media import media_url
from apps.common.question_display import difficulty_label
from apps.parser.models import ExamQuestion
from .models import PracticePoolItem


ALGORITHM_VERSION = 'wrongbook-candidate-v1'
DIFFICULTY_RULE = 'same_or_within_one_star'
QUESTION_TYPE_LABELS = ExamQuestion.QUESTION_TYPE_LABELS


def normalize_stage(value) -> str | None:
    """Normalize the paper stage to the two stages used by this feature."""
    if value is None:
        return None
    text = str(value).strip().lower().replace(' ', '').replace('_', '').replace('-', '')
    if not text:
        return None
    if text in {'初中', '初中阶段', 'junior', 'juniorhigh', 'middle', 'middleschool'}:
        return '初中'
    if text in {'高中', '高中阶段', 'senior', 'seniorhigh', 'high', 'highschool'}:
        return '高中'
    return None


def _flatten_knowledge_points(raw):
    if isinstance(raw, dict):
        raw = raw.get('points', raw.get('knowledge_points', []))
    if raw is None:
        return []
    if isinstance(raw, (str, int, float)):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return list(raw)
    return []


def normalize_knowledge_points(raw) -> list[dict]:
    """Normalize historical knowledge-point JSON without changing its meaning."""
    normalized = []
    for item in _flatten_knowledge_points(raw):
        if isinstance(item, dict):
            point = {}
            for field in ('id', 'module', 'name'):
                value = item.get(field)
                if value is not None and str(value).strip():
                    point[field] = str(value).strip()
            if point:
                normalized.append(point)
        elif str(item).strip():
            normalized.append({'name': str(item).strip()})
    return normalized


def knowledge_point_keys(points) -> set[str]:
    """Return matching keys, preferring id, then module, then name."""
    keys = set()
    for point in normalize_knowledge_points(points):
        for field in ('id', 'module', 'name'):
            value = point.get(field)
            if value:
                keys.add(f'{field}:{value}')
                break
    return keys


def knowledge_point_labels(points) -> list[str]:
    labels = []
    for point in normalize_knowledge_points(points):
        point_labels = [point.get(field) for field in ('module', 'name') if point.get(field)]
        if not point_labels and point.get('id'):
            point_labels = [point['id']]
        for value in point_labels:
            if value and value not in labels:
                labels.append(value)
    return labels


def normalize_difficulty_star(value) -> int | None:
    """Convert supported difficulty values to a 1-5 star integer."""
    if value is None or str(value).strip() == '':
        return None
    text = str(value).strip().upper()
    level_match = re.fullmatch(r'L\s*([1-5])', text)
    if level_match:
        return int(level_match.group(1))
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not number.is_finite() or number < 1 or number > 5:
        return None
    return int(number.quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def normalize_tags(raw) -> list[str]:
    if raw is None:
        return []
    values = raw if isinstance(raw, (list, tuple)) else re.split(r'[,，]', str(raw))
    tags = []
    for value in values:
        text = str(value or '').strip()
        if text and text not in tags:
            tags.append(text)
    return tags


def question_display(q: ExamQuestion) -> dict:
    """Build the safe metadata shown on a candidate card.

    Answers and explanations are intentionally omitted.
    """
    points = normalize_knowledge_points(q.knowledge_points)
    return {
        'id': str(q.id),
        'question_no': q.question_no,
        'question_type': q.question_type,
        'question_type_label': QUESTION_TYPE_LABELS.get(q.question_type, q.question_type),
        'difficulty': float(q.difficulty) if q.difficulty is not None else None,
        'difficulty_label': difficulty_label(q.difficulty),
        'stage': normalize_stage(getattr(q.paper, 'stage', None)),
        'subject': q.subject,
        'knowledge_points': points,
        'knowledge_point_labels': knowledge_point_labels(points),
        'tags': normalize_tags(q.tags),
        'stem': q.stem,
        'stem_html': q.stem_html,
        'images': [
            {
                'id': str(image.id),
                'url': media_url(image.file_path),
                'file_path': image.file_path,
                'image_type': image.image_type,
                'display_width': image.display_width,
                'description': image.description or '',
            }
            for image in q.images.all().order_by('sort_order')
            if image.file_path and image.image_type != 'formula'
        ],
        'options': [
            {'label': option.option_label, 'content': option.content}
            for option in q.options.all().order_by('sort_order')
        ],
    }


def _difficulty_match(original_star: int, candidate_star: int) -> tuple[int, str, int]:
    delta = candidate_star - original_star
    if delta == 0:
        return 0, 'same', delta
    if delta > 0:
        return 1, 'slightly_harder', delta
    return 2, 'slightly_easier', delta


class WrongbookCandidateProvider:
    def recommend_for_wrong_item(self, *, student, wrong_item, limit=3):
        raise NotImplementedError


class QuestionBankWrongbookCandidateProvider(WrongbookCandidateProvider):
    """Recommend candidates from the visible question bank."""

    def _visible_questions(self):
        return (
            ExamQuestion.objects
            .filter(paper__is_deleted=False, review_status__in=('reviewed', 'confirmed'), need_review=False)
            .exclude(stem__isnull=True)
            .exclude(stem='')
            .select_related('paper')
            .prefetch_related('images', 'options')
        )

    def recommend_for_wrong_item(self, *, student, wrong_item, limit=3):
        original = (
            ExamQuestion.objects.select_related('paper').prefetch_related('images', 'options')
            .filter(pk=wrong_item.question_id).first()
        )
        if original is None:
            return {
                'items': [],
                'meta': {
                    'original': {'id': str(wrong_item.id), 'question': None},
                    'stage': None,
                    'difficulty_rule': DIFFICULTY_RULE,
                    'limit': limit,
                    'returned_count': 0,
                    'insufficient_reason': '原题不存在',
                    'algorithm_version': ALGORITHM_VERSION,
                },
            }

        original_display = question_display(original)
        original_display['question_id'] = str(original.id)
        original_stage = normalize_stage(original.paper.stage)
        original_star = normalize_difficulty_star(original.difficulty)
        original_keys = knowledge_point_keys(original.knowledge_points)
        metadata_fallback = not original_keys
        required_count = 1 if len(original_keys) == 1 else (2 if original_keys else 0)
        reasons = []
        if original_stage is None:
            reasons.append('原题学段缺失或无法识别')
        if original_star is None:
            reasons.append('原题难度缺失或无法转换为星级')
        if not original_keys:
            reasons.append('原题没有有效知识点')

        # Historical questions without knowledge-point metadata still need a
        # usable recommendation. Retain stage/subject/difficulty constraints
        # and rank same-type questions first in this fallback mode.
        if metadata_fallback and reasons:
            reasons.pop()

        active_pool_ids = set(
            PracticePoolItem.objects.filter(student_user=student, status='active')
            .values_list('question_id', flat=True)
        )
        matched = []
        if not reasons:
            for candidate in self._visible_questions():
                if candidate.id == original.id or candidate.id in active_pool_ids:
                    continue
                if original.subject and str(candidate.subject or '').strip() != str(original.subject).strip():
                    continue
                if normalize_stage(candidate.paper.stage) != original_stage:
                    continue
                candidate_star = normalize_difficulty_star(candidate.difficulty)
                if candidate_star is None or abs(candidate_star - original_star) > 1:
                    continue
                candidate_keys = knowledge_point_keys(candidate.knowledge_points)
                matched_keys = original_keys & candidate_keys
                same_question_type = str(candidate.question_type or '').strip().lower() == str(original.question_type or '').strip().lower()
                if original_keys and len(matched_keys) < required_count:
                    continue
                difficulty_rank, difficulty_match, difficulty_delta = _difficulty_match(
                    original_star, candidate_star
                )
                matched.append({
                    'question': candidate,
                    'matched_count': len(matched_keys),
                    'question_type_rank': 0 if same_question_type else 1,
                    'same_question_type': same_question_type,
                    'difficulty_rank': difficulty_rank,
                    'difficulty_match': difficulty_match,
                    'difficulty_delta': difficulty_delta,
                })

        matched.sort(key=lambda item: (
            -item['matched_count'],
            item['question_type_rank'],
            item['difficulty_rank'],
            item['question'].sort_order,
            str(item['question'].id),
        ))
        items = []
        for item in matched[:limit]:
            candidate = question_display(item['question'])
            candidate['match'] = {
                'matched_knowledge_point_count': item['matched_count'],
                'required_knowledge_point_count': required_count,
                'same_stage': True,
                'same_question_type': item['same_question_type'],
                'difficulty_delta': item['difficulty_delta'],
                'difficulty_match': item['difficulty_match'],
                'already_in_practice_pool': False,
            }
            items.append(candidate)

        if len(items) < limit:
            reasons.append(f'符合严格规则的候选题不足{limit}道，实际返回{len(items)}道')
        return {
            'items': items,
            'meta': {
                'original': {'id': str(wrong_item.id), 'question': original_display},
                'stage': original_stage,
                'difficulty_rule': DIFFICULTY_RULE,
                'limit': limit,
                'returned_count': len(items),
                'insufficient_reason': '；'.join(reasons) if reasons else None,
                'recommendation_mode': 'metadata_fallback' if metadata_fallback else 'knowledge_point_match',
                'algorithm_version': ALGORITHM_VERSION,
            },
        }
