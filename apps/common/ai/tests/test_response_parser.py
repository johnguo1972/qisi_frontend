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


def test_response_parser_redacts_json_secrets_and_bare_base64_before_truncating():
    bare_base64 = "QWxhZGRpbjpvcGVuIHNlc2FtZQ+/" * 4
    bare_base64url = "AbC9_def-GhiJklMNopQRstuVwXyZ0123" * 3
    raw = (
        'broken-prefix "key": "short-secret", '
        '"api_key": "AIzaSensitiveValue", '
        '"token": "token-sensitive", '
        '"secret": "secret-sensitive", '
        '"authorization": "Basic auth-sensitive" '
        + bare_base64
        + " "
        + bare_base64url
    )

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    formatted = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    assert "broken-prefix" in formatted
    for sensitive in (
        "AIzaSensitiveValue",
        "short-secret",
        "token-sensitive",
        "secret-sensitive",
        "auth-sensitive",
        bare_base64,
        bare_base64url,
    ):
        assert sensitive not in formatted
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    ("field", "scheme", "credential"),
    [
        ("authorization", "Bearer", "bearer-short-secret"),
        ('"authorization"', "Basic", "basic-short-secret"),
        ("'authorization'", "Digest", "digest-short-secret"),
    ],
)
def test_response_parser_redacts_complete_bare_authorization_values(
    field, scheme, credential
):
    raw = f"broken-prefix {field}: {scheme} {credential}, trailing"

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    formatted = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    assert credential not in str(caught.value)
    assert credential not in formatted
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_response_parser_redacts_all_bare_digest_parameters_before_truncating():
    safe_prefix = "broken-prefix-" + "safe." * 12
    sensitive_values = (
        "digest-user-sensitive",
        "digest-realm-sensitive",
        "digest-nonce-sensitive",
        "/private/resource",
        "digest-response-sensitive",
        "digest-opaque-sensitive",
        "digest-cnonce-sensitive",
    )
    raw = (
        f'{safe_prefix} authorization: Digest username="{sensitive_values[0]}", '
        f'realm="{sensitive_values[1]}", nonce="{sensitive_values[2]}", '
        f'uri="{sensitive_values[3]}", response="{sensitive_values[4]}", '
        f'opaque="{sensitive_values[5]}", qop=auth, nc=00000001, '
        f'cnonce="{sensitive_values[6]}"; ordinary-note-visible'
    )

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    formatted = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    assert safe_prefix in str(caught.value)
    assert "ordinary-note-visible" in str(caught.value)
    for sensitive in sensitive_values:
        assert sensitive not in str(caught.value)
        assert sensitive not in formatted
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


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
