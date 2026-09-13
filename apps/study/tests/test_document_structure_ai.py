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
