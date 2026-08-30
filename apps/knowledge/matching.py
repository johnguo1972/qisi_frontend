"""Deterministic first-phase question to knowledge-point matching."""
import re
from decimal import Decimal

from apps.common.subject_codes import normalize_subject_code
from .models import KnowledgePoint, QuestionKnowledgeMatch
from .teacher_scope import STAGE_ALIASES, normalize_stage_codes

RULE_VERSION = 'rule-v1'


def _text(question):
    values = [
        question.stem, question.stem_html, question.material,
        question.section_title, question.source_collection,
    ]
    values.append(' '.join(str(item) for item in (question.tags or []) if item))
    return ' '.join(str(value or '') for value in values).lower()


def _paper_stage_codes(question):
    paper = question.paper
    raw = f'{paper.stage or ""},{paper.grade or ""}'.lower()
    result = []
    for alias, code in STAGE_ALIASES.items():
        if alias.lower() in raw and code not in result:
            result.append(code)
    # Numeric grades are common in imported papers.
    numbers = [int(item) for item in re.findall(r'(?<!\d)([1-9]|1[0-2])(?!\d)', raw)]
    if numbers:
        result.append('primary' if max(numbers) <= 6 else 'junior' if max(numbers) <= 9 else 'senior')
    return result


def _paper_grade_indexes(question):
    """Extract an exact grade when the paper carries one."""
    raw = f'{question.paper.grade or ""},{question.paper.stage or ""}'.strip().lower()
    numbers = [int(item) for item in re.findall(r'(?<!\d)([1-9]|1[0-2])(?!\d)', raw)]
    if numbers:
        return set(numbers)
    chinese = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
        '七': 7, '八': 8, '九': 9, '十': 10,
    }
    for prefix, number in (('高', None), ('初三', 9), ('初二', 8), ('初一', 7)):
        if prefix == '高' and '高' in raw:
            found = re.search(r'高([一二三123])', raw)
            if found:
                value = found.group(1)
                return {10 + chinese.get(value, int(value) if value.isdigit() else 0) - 1}
        elif prefix in raw:
            return {number}
    for word, number in chinese.items():
        if f'{word}年级' in raw:
            return {number}
    return set()


def _candidate_points(question, teacher_stages=()):
    subject = normalize_subject_code(question.subject or question.paper.subject)
    if not subject:
        return KnowledgePoint.objects.none()
    qs = KnowledgePoint.objects.filter(subject=subject)
    allowed_stages = set(normalize_stage_codes(teacher_stages))
    paper_stages = set(_paper_stage_codes(question))
    if allowed_stages:
        qs = qs.filter(stage__in=allowed_stages)
    if paper_stages:
        qs = qs.filter(stage__in=paper_stages)
    paper_grades = _paper_grade_indexes(question)
    if paper_grades:
        qs = qs.filter(grade_index__in=paper_grades)
    return qs


def suggest_matches(question, teacher_stages=()):
    """Return rule suggestions, including one explicit unmatched result."""
    text = _text(question)
    results = []
    for point in _candidate_points(question, teacher_stages).iterator():
        fields = [('module', point.module), ('chapter', point.chapter), ('content', point.content)]
        matched = [name for name, value in fields if value and str(value).lower() in text]
        if not matched:
            continue
        score = Decimal('0.9500') if 'module' in matched else Decimal('0.8000')
        if 'content' in matched and score < Decimal('0.7000'):
            score = Decimal('0.7000')
        results.append({
            'knowledge_point': point,
            'confidence': score,
            'evidence': {'matched_fields': matched, 'rule_version': RULE_VERSION},
        })
    results.sort(key=lambda item: (-item['confidence'], item['knowledge_point'].id))
    if not results:
        results.append({
            'knowledge_point': None,
            'confidence': Decimal('0.0000'),
            'evidence': {'matched_fields': [], 'reason': 'no_rule_match', 'rule_version': RULE_VERSION},
        })
    return results


def rebuild_question_matches(question, teacher_stages=()):
    QuestionKnowledgeMatch.objects.filter(
        question=question, source='rule', source_version=RULE_VERSION,
    ).delete()
    return [QuestionKnowledgeMatch.objects.create(
        question=question,
        knowledge_point=item['knowledge_point'],
        source='rule', source_version=RULE_VERSION,
        confidence=item['confidence'], status='suggested', evidence=item['evidence'],
    ) for item in suggest_matches(question, teacher_stages)]
