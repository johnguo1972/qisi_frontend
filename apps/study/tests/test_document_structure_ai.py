from apps.study import document_structure_ai as module
from apps.study.document_import_service import DocumentAssetRef, ExtractedQuestionFragment


def test_structure_candidate_strips_fences_and_returns_required_structure(monkeypatch):
    """A fenced but valid Qwen response becomes one validated import candidate."""
    monkeypatch.setattr(
        module,
        '_complete_structure',
        lambda _candidate, model: '''```json
        {"question_no":"7","question_type":"single_choice","stem":"Choose one.",
        "options":[{"label":"A","content":"One"}],"answer":"A","analysis":"Only A is one.",
        "tables":[],"illustrations":[],"confidence":0.91,"review_reason":""}
        ```''',
    )

    result = module.structure_candidate(
        ExtractedQuestionFragment(question_no='7', text='7. Choose one.'),
    )

    assert result.question_no == '7'
    assert result.question_type == 'single_choice'
    assert result.options == [{'label': 'A', 'content': 'One'}]
    assert result.confidence == 0.91


def test_structure_candidate_retries_one_asset_read_failure(monkeypatch):
    """A transient asset read error receives exactly one retry before the candidate is dropped."""
    responses = iter([
        OSError('asset is temporarily unavailable'),
        '{"question_no":"8","question_type":"fill_blank","stem":"Fill it.",'
        '"options":[],"answer":"one","analysis":"The blank is one.",'
        '"tables":[],"illustrations":[],"confidence":0.8,"review_reason":""}',
    ])

    def complete(_candidate, _model):
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(module, '_complete_structure', complete)

    result = module.structure_candidate(
        ExtractedQuestionFragment(question_no='8', text='8. Fill it.'),
    )

    assert result.question_no == '8'


def test_validated_question_normalizes_nullable_text_and_table_fields():
    """Qwen's harmless null text/table noise must not discard an otherwise usable question."""
    candidate = ExtractedQuestionFragment(question_no='9', text='9. Choose one.')
    parsed = {
        'question_no': 9, 'question_type': 'single_choice', 'stem': 'Choose one.',
        'options': [{'label': 'A', 'content': 'One'}], 'answer': None, 'analysis': None,
        'tables': None, 'illustrations': [], 'confidence': '0.7', 'review_reason': None,
    }

    result = module._validated_question(parsed, candidate)

    assert result.answer == ''
    assert result.analysis == ''
    assert result.review_reason == ''
    assert result.tables == []


def test_validated_question_resolves_reference_and_drops_unknown_illustrations():
    """Known source references are safe; hallucinated assets are omitted instead of dropping the question."""
    candidate = ExtractedQuestionFragment(
        question_no='10', text='10. Diagram.',
        asset_refs=[DocumentAssetRef(reference='docx:word/media/image1.png')],
    )
    parsed = {
        'question_no': '10', 'question_type': 'single_choice', 'stem': 'Diagram.',
        'options': [], 'answer': '', 'analysis': '', 'tables': [], 'confidence': 0.8,
        'review_reason': '',
        'illustrations': [
            {'reference': 'docx:word/media/image1.png'},
            {'file': 'hallucinated.png'},
        ],
    }

    result = module._validated_question(
        parsed, candidate, {'docx:word/media/image1.png': 'document-known.png'},
    )

    assert result.illustrations == [{
        'file': 'document-known.png', 'reference': 'docx:word/media/image1.png',
        'placement': 'stem',
    }]


def test_validated_question_preserves_every_extracted_asset_when_qwen_omits_it():
    """Source images are authoritative even when Qwen returns no illustrations."""
    candidate = ExtractedQuestionFragment(
        question_no='11', text='11. Diagram.',
        asset_refs=[DocumentAssetRef(
            reference='pdf:42', page_no=3, bbox=(10.0, 20.0, 110.0, 220.0),
        )],
    )
    parsed = {
        'question_no': '11', 'question_type': 'single_choice', 'stem': 'Diagram.',
        'options': [], 'answer': '', 'analysis': '', 'tables': [], 'confidence': 0.8,
        'review_reason': '', 'illustrations': [],
    }

    result = module._validated_question(parsed, candidate, {'pdf:42': 'document-42.png'})

    assert result.illustrations == [{
        'file': 'document-42.png', 'reference': 'pdf:42', 'bbox': [10.0, 20.0, 110.0, 220.0],
        'placement': 'stem', 'source_page': 3,
    }]
