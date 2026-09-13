"""Qwen-backed structural normalization for one extracted document candidate."""

from __future__ import annotations

import json
from dataclasses import dataclass

from apps.common.ai.client import AIClient
from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.prompt_registry import PromptRegistry
from apps.common.ai.response_parser import ResponseParser
from apps.common.exceptions import AIRequestError
from apps.study.document_import_service import ExtractedQuestionFragment


REQUIRED_FIELDS = {
    'question_no', 'question_type', 'stem', 'options', 'answer', 'analysis',
    'tables', 'illustrations', 'confidence', 'review_reason',
}


@dataclass(frozen=True)
class StructuredQuestion:
    question_no: str
    question_type: str
    stem: str
    options: list[dict]
    answer: str
    analysis: str
    tables: list
    illustrations: list[dict]
    confidence: float
    review_reason: str
    page_start: int = 1
    page_end: int = 1

    def to_ingestion_data(self) -> dict:
        return {
            'question_no': self.question_no,
            'question_type': self.question_type,
            'stem': self.stem,
            'options': self.options,
            'answer': self.answer,
            'analysis': self.analysis,
            'tables': self.tables,
            'illustrations': self.illustrations,
            'quality': {'requires_review': bool(self.review_reason)},
            'source': {'page_start': self.page_start, 'page_end': self.page_end},
        }


def _candidate_payload(candidate: ExtractedQuestionFragment) -> dict:
    return {
        'question_no': candidate.question_no,
        'text': candidate.text,
        'tables': candidate.tables,
        'page_start': candidate.page_range[0],
        'page_end': candidate.page_range[1],
        'assets': [
            {'reference': item.reference, 'page_no': item.page_no, 'bbox': item.bbox}
            for item in candidate.asset_refs
        ],
    }


def _complete_structure(candidate, model):
    if model != 'qwen3.7-plus':
        raise ValueError('document structure model must be qwen3.7-plus')
    payload = _candidate_payload(candidate)
    registry = PromptRegistry()
    system, user = registry.render('document_structure', candidate_json=json.dumps(payload, ensure_ascii=False))
    with AIClient() as client:
        return client.complete('document_structure', system=system, user=user).content


def _validated_question(parsed, candidate) -> StructuredQuestion:
    if not isinstance(parsed, dict) or set(parsed) != REQUIRED_FIELDS:
        raise AIResponseError('document structure response does not match the required schema')
    if not isinstance(parsed['question_no'], (str, int)) or not str(parsed['question_no']).strip():
        raise AIResponseError('document structure response has no question number')
    if not isinstance(parsed['question_type'], str) or not parsed['question_type'].strip():
        raise AIResponseError('document structure response has no question type')
    if not isinstance(parsed['stem'], str) or not parsed['stem'].strip():
        raise AIResponseError('document structure response has no stem')
    if not isinstance(parsed['options'], list) or any(
        not isinstance(item, dict) or not isinstance(item.get('label'), str)
        or not isinstance(item.get('content'), str) for item in parsed['options']
    ):
        raise AIResponseError('document structure response has invalid options')
    if not all(isinstance(parsed[name], str) for name in ('answer', 'analysis', 'review_reason')):
        raise AIResponseError('document structure response has invalid text fields')
    if not isinstance(parsed['tables'], list) or not isinstance(parsed['illustrations'], list):
        raise AIResponseError('document structure response has invalid assets')
    if any(not isinstance(asset, dict) for asset in parsed['illustrations']):
        raise AIResponseError('document structure response has invalid assets')
    try:
        confidence = float(parsed['confidence'])
    except (TypeError, ValueError):
        raise AIResponseError('document structure response has invalid confidence') from None
    if not 0 <= confidence <= 1:
        raise AIResponseError('document structure response has invalid confidence')
    return StructuredQuestion(
        question_no=str(parsed['question_no']).strip(), question_type=parsed['question_type'].strip(),
        stem=parsed['stem'].strip(), options=parsed['options'], answer=parsed['answer'],
        analysis=parsed['analysis'], tables=parsed['tables'], illustrations=parsed['illustrations'],
        confidence=confidence, review_reason=parsed['review_reason'],
        page_start=candidate.page_range[0], page_end=candidate.page_range[1],
    )


def structure_candidate(candidate, model='qwen3.7-plus') -> StructuredQuestion:
    """Request and validate structure, retrying a provider/schema failure once."""
    last_error = None
    for _attempt in range(2):
        try:
            return _validated_question(ResponseParser.parse_json(_complete_structure(candidate, model)), candidate)
        except (AIResponseError, AIRequestError, OSError) as exc:
            last_error = exc
    raise last_error or AIResponseError('document structure request failed')
