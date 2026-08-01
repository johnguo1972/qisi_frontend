from __future__ import annotations

import traceback

import pytest
from pydantic import BaseModel

from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.response_parser import ResponseParser


class AnswerSchema(BaseModel):
    answer: str


def test_response_parser_repairs_fenced_json():
    parsed = ResponseParser.parse_json('```json\n{"answer":"D",}\n```')

    assert parsed == {"answer": "D"}


def test_response_parser_preserves_array_top_level():
    parsed = ResponseParser.parse_json(
        '说明：\n```json\n[{"answer":"A",}, {"answer":"B"}]\n```'
    )

    assert parsed == [{"answer": "A"}, {"answer": "B"}]


def test_response_parser_extracts_first_choice_content():
    payload = {
        "choices": [{"message": {"role": "assistant", "content": "ok"}}]
    }

    assert ResponseParser.extract_content(payload) == "ok"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [{}]},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": 123}}]},
    ],
)
def test_response_parser_rejects_missing_choice_content(payload):
    with pytest.raises(AIResponseError, match="content"):
        ResponseParser.extract_content(payload)


def test_response_parser_rejects_irrecoverable_json_with_truncated_preview():
    raw = "not-json-" + "x" * 500 + "UNREACHABLE_TAIL"

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    assert "not-json" in str(caught.value)
    assert "UNREACHABLE_TAIL" not in str(caught.value)
    assert len(str(caught.value)) < 300
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_response_parser_redacts_secrets_base64_and_pii_from_errors():
    raw = (
        'broken sk-live-sensitive-token Bearer abc.def.ghi '
        '13812345678 user@example.test data:image/png;base64,AAAAAA'
    )

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    formatted = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    for sensitive in (
        "sk-live-sensitive-token",
        "abc.def.ghi",
        "13812345678",
        "user@example.test",
        "AAAAAA",
    ):
        assert sensitive not in formatted


def test_response_parser_validates_and_returns_schema_dump():
    parsed = ResponseParser.parse_json('{"answer": "D"}', AnswerSchema)

    assert parsed == {"answer": "D"}


def test_response_parser_wraps_schema_errors_without_raw_data():
    marker = "student-private-answer"

    with pytest.raises(AIResponseError, match="schema") as caught:
        ResponseParser.parse_json(
            '{"unexpected": "' + marker + '"}', AnswerSchema
        )

    assert marker not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
