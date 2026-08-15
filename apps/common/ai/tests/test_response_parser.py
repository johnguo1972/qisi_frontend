from __future__ import annotations

import traceback

import pytest
from pydantic import BaseModel

from apps.common.ai.exceptions import AIResponseError
from apps.common.ai.response_parser import ResponseParser


class AnswerSchema(BaseModel):
    answer: str


def _error_surfaces(error: AIResponseError) -> tuple[str, str]:
    formatted = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )
    assert error.__cause__ is None
    assert error.__context__ is None
    return str(error), formatted


def test_response_parser_repairs_fenced_json():
    parsed = ResponseParser.parse_json('```json\n{"answer":"D",}\n```')

    assert parsed == {"answer": "D"}


def test_response_parser_preserves_single_escaped_latex_commands():
    parsed = ResponseParser.parse_json(
        r'{"answer":"$\\frac{2}{3} \\times t$"}'
    )

    assert parsed == {"answer": r"$\frac{2}{3} \times t$"}


def test_response_parser_preserves_array_top_level():
    parsed = ResponseParser.parse_json(
        '说明：\n```json\n[{"answer":"A",}, {"answer":"B"}]\n```'
    )

    assert parsed == [{"answer": "A"}, {"answer": "B"}]


def test_response_parser_keeps_first_complete_object_before_tail_fragment():
    parsed = ResponseParser.parse_json(
        '{"answer":"B"} {"partial":{"detail":"unfinished"}'
    )

    assert parsed == {"answer": "B"}


def test_response_parser_ignores_braces_and_escapes_inside_first_object_string():
    parsed = ResponseParser.parse_json(
        r'{"answer":"literal { and } quote \" and slash \\ done"} '
        r'{"partial":{"detail":"unfinished"}'
    )

    assert parsed == {
        "answer": 'literal { and } quote " and slash \\ done'
    }


def test_response_parser_keeps_first_complete_array_before_tail_fragment():
    parsed = ResponseParser.parse_json(
        '[{"answer":"A"}] [{"partial":["unfinished"]'
    )

    assert parsed == [{"answer": "A"}]


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


@pytest.mark.parametrize("boundary", [";", "}", "]"])
def test_response_parser_preserves_digest_credential_boundaries(boundary):
    sensitive_values = (
        "digest-double-sensitive",
        "digest-single-sensitive",
        "digest-bare-sensitive",
    )
    raw = (
        'broken authorization: Digest username="prefix\\"'
        f'{sensitive_values[0]}", '
        "realm='prefix\\'"
        f"{sensitive_values[1]}', qop=auth, "
        f"x.ext={sensitive_values[2]}{boundary} ordinary-boundary-visible"
    )

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    formatted = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    for sensitive in sensitive_values:
        assert sensitive not in str(caught.value)
        assert sensitive not in formatted
    assert "ordinary-boundary-visible" in str(caught.value)
    assert "ordinary-boundary-visible" in formatted
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "extension_name",
    [
        "_ext",
        "9ext",
        "!ext",
        "#ext",
        "$ext",
        "%ext",
        "&ext",
        "x'ext",
        "x*",
        "x+ext",
        "x.ext",
        "x^ext",
        "x`ext",
        "x|ext",
        "x~ext",
    ],
)
def test_response_parser_redacts_digest_extensions_with_http_token_names(
    extension_name,
):
    sensitive = "digest-extension-sensitive"
    raw = (
        'broken authorization: Digest username="user-sensitive", '
        f'{extension_name}="{sensitive}"; ordinary-note-visible'
    )

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    formatted = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    assert sensitive not in str(caught.value)
    assert sensitive not in formatted
    assert "ordinary-note-visible" in str(caught.value)
    assert "ordinary-note-visible" in formatted
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize("line_break", ["\n", "\r\n"])
def test_response_parser_digest_parameter_spacing_does_not_cross_lines(
    line_break,
):
    digest_secret = "digest-line-sensitive"
    ordinary_value = "ordinary-value-visible"
    raw = (
        f'broken authorization: Digest username="{digest_secret}",'
        f"{line_break}ordinary={ordinary_value}; trailing-visible"
    )

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    formatted = "".join(
        traceback.format_exception(
            type(caught.value), caught.value, caught.value.__traceback__
        )
    )
    assert digest_secret not in str(caught.value)
    assert digest_secret not in formatted
    assert ordinary_value in str(caught.value)
    assert ordinary_value in formatted
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize("line_break", ["\n", "\r\n"])
@pytest.mark.parametrize("quote", ['"', "'"])
def test_response_parser_quoted_authorization_does_not_cross_lines(
    quote, line_break
):
    sensitive = "quoted-authorization-sensitive"
    ordinary = "ordinary-diagnostic-visible"
    raw = (
        f"broken authorization: {quote}Digest username={sensitive}"
        f"{line_break}{ordinary}{quote}; trailing-visible"
    )

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    message, formatted = _error_surfaces(caught.value)
    assert sensitive not in message
    assert sensitive not in formatted
    assert ordinary in message
    assert ordinary in formatted


@pytest.mark.parametrize("line_break", ["\n", "\r\n"])
@pytest.mark.parametrize("scheme", ["Bearer", "Basic", "Digest"])
def test_response_parser_bare_authorization_does_not_cross_lines(
    scheme, line_break
):
    sensitive = "bare-authorization-sensitive"
    ordinary = "ordinary-diagnostic-visible"
    raw = (
        f"broken authorization: {scheme} {sensitive}"
        f"{line_break}{ordinary}; trailing-visible"
    )

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    message, formatted = _error_surfaces(caught.value)
    assert sensitive not in message
    assert sensitive not in formatted
    assert ordinary in message
    assert ordinary in formatted


def test_response_parser_redacts_strict_lowercase_base64url_token():
    sensitive = "abcd-efgabcd-efgabcd-efgabcd-efg"
    ordinary = "ordinary diagnostic words remain visible"
    raw = f"broken {sensitive} {ordinary}"

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    message, formatted = _error_surfaces(caught.value)
    assert sensitive not in message
    assert sensitive not in formatted
    assert ordinary in message
    assert ordinary in formatted


def test_response_parser_preserves_plain_long_english_diagnostic():
    ordinary = "ordinarydiagnosticmessagewithlowercaseletters"

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json("broken " + ordinary)

    message, formatted = _error_surfaces(caught.value)
    assert ordinary in message
    assert ordinary in formatted


@pytest.mark.parametrize(
    ("prefix", "field"),
    [
        ("", "key"),
        ("broken ", "token"),
        ("broken (", "secret"),
    ],
)
def test_response_parser_redacts_exact_secret_fields_with_equals(
    prefix, field
):
    sensitive = "shortsensitivevalue"
    ordinary = "ordinary-visible"
    raw = f"{prefix}{field}={sensitive}; {ordinary}"

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(raw)

    message, formatted = _error_surfaces(caught.value)
    assert sensitive not in message
    assert sensitive not in formatted
    assert ordinary in message
    assert ordinary in formatted


@pytest.mark.parametrize(
    "assignment",
    [
        "api_key=shortapivalue",
        "access_token=shortaccessvalue",
        'key: "shortkeyvalue"',
        "token: shorttokenvalue",
        "secret: shortsecretvalue",
    ],
)
def test_response_parser_keeps_existing_secret_field_forms_redacted(
    assignment
):
    sensitive = assignment.split("=", 1)[-1].split(":", 1)[-1]
    sensitive = sensitive.strip().strip('"')
    ordinary = "ordinary-visible"

    with pytest.raises(AIResponseError) as caught:
        ResponseParser.parse_json(f"broken {assignment}; {ordinary}")

    message, formatted = _error_surfaces(caught.value)
    assert sensitive not in message
    assert sensitive not in formatted
    assert ordinary in message
    assert ordinary in formatted


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
