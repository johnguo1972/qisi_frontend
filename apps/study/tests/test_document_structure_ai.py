from apps.study import document_structure_ai as module
from apps.study.document_import_service import ExtractedQuestionFragment


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
