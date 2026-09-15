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


def _candidate_payload(candidate: ExtractedQuestionFragment, asset_files=None) -> dict:
    asset_files = asset_files or {}
    return {
        'question_no': candidate.question_no,
        'text': candidate.text,
        'tables': candidate.tables,
        'page_start': candidate.page_range[0],
        'page_end': candidate.page_range[1],
        'assets': [
            {
                'reference': item.reference,
                'file': asset_files.get(item.reference),
                'page_no': item.page_no,
                'bbox': item.bbox,
            }
            for item in candidate.asset_refs
        ],
    }


def _complete_structure(candidate, model, asset_files=None):
    if model != 'qwen3.7-plus':
        raise ValueError('document structure model must be qwen3.7-plus')
    payload = _candidate_payload(candidate, asset_files)
    registry = PromptRegistry()
    system, user = registry.render('document_structure', candidate_json=json.dumps(payload, ensure_ascii=False))
    with AIClient() as client:
        return client.complete('document_structure', system=system, user=user).content


def _validated_question(parsed, candidate, asset_files=None) -> StructuredQuestion:
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
    text_fields = {}
    for name in ('answer', 'analysis', 'review_reason'):
        value = parsed[name]
        if value is None:
            text_fields[name] = ''
        elif isinstance(value, str):
            text_fields[name] = value
        else:
            raise AIResponseError('document structure response has invalid text fields')
    tables = parsed['tables']
    if tables is None:
        tables = []
    elif isinstance(tables, dict):
        tables = [tables]
    elif not isinstance(tables, list):
        raise AIResponseError('document structure response has invalid assets')
    illustrations = parsed['illustrations']
    if illustrations is None:
        illustrations = []
    if not isinstance(illustrations, list):
        raise AIResponseError('document structure response has invalid assets')
    known_assets = asset_files or {}
    allowed_files = set(known_assets.values())
    normalized_illustrations = []
    for asset in illustrations:
        if not isinstance(asset, dict):
            continue
        file_name = asset.get('file')
        if file_name not in allowed_files:
            file_name = known_assets.get(asset.get('reference'))
        if file_name in allowed_files:
            normalized_illustrations.append({'file': file_name})
    try:
        confidence = float(parsed['confidence'])
    except (TypeError, ValueError):
        raise AIResponseError('document structure response has invalid confidence') from None
    if not 0 <= confidence <= 1:
        raise AIResponseError('document structure response has invalid confidence')
    return StructuredQuestion(
        question_no=str(parsed['question_no']).strip(), question_type=parsed['question_type'].strip(),
        stem=parsed['stem'].strip(), options=parsed['options'], answer=text_fields['answer'],
        analysis=text_fields['analysis'], tables=tables, illustrations=normalized_illustrations,
        confidence=confidence, review_reason=text_fields['review_reason'],
        page_start=candidate.page_range[0], page_end=candidate.page_range[1],
    )


def structure_candidate(candidate, model='qwen3.7-plus', *, asset_files=None) -> StructuredQuestion:
    """Request and validate structure, retrying a provider/schema failure once."""
    last_error = None
    for _attempt in range(2):
        try:
            raw_response = (
                _complete_structure(candidate, model, asset_files)
                if asset_files else _complete_structure(candidate, model)
            )
            return _validated_question(
                ResponseParser.parse_json(raw_response),
                candidate,
                asset_files,
            )
        except (AIResponseError, AIRequestError, OSError) as exc:
            last_error = exc
    raise last_error or AIResponseError('document structure request failed')
