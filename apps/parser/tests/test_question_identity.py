import re

import pytest

from apps.parser.question_identity import (
    activate_content_fingerprint,
    build_content_fingerprint,
    reserve_content_fingerprint,
)
from apps.parser.models import ExamQuestion, QuestionContentFingerprint
from apps.papers.models import ExamPaper


def test_content_fingerprint_is_stable_for_equivalent_unicode_and_whitespace():
    """Removing NFKC or whitespace normalization must change this result."""
    fingerprint = build_content_fingerprint(
        stem="  求\u3000x＝２\r\n的值。 ",
        options=["A.  ２", "B.\t3"],
        formula_texts=[r"\\frac{1}{2}"],
        image_hashes=["a" * 64],
    )

    equivalent_fingerprint = build_content_fingerprint(
        stem="求 x=2 的值。",
        options=["A. 2", "B. 3"],
        formula_texts=[r"\\frac{1}{2}"],
        image_hashes=["a" * 64],
    )

    assert fingerprint == equivalent_fingerprint
    assert re.fullmatch(r"[0-9a-f]{64}", fingerprint)


@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    (
        ("options", ["B. 3", "A. 2"]),
        ("formula_texts", [r"\\sqrt{x}", r"\\frac{1}{2}"]),
        ("image_hashes", ["b" * 64, "a" * 64]),
    ),
)
def test_content_fingerprint_preserves_order_for_content_parts(
    changed_field, changed_value
):
    """Sorting any fingerprint input list would incorrectly make this pass."""
    baseline = {
        "stem": "求 x=2 的值。",
        "options": ["A. 2", "B. 3"],
        "formula_texts": [r"\\frac{1}{2}", r"\\sqrt{x}"],
        "image_hashes": ["a" * 64, "b" * 64],
    }
    changed = {**baseline, changed_field: changed_value}

    assert build_content_fingerprint(**baseline) != build_content_fingerprint(**changed)


@pytest.mark.django_db
def test_second_reservation_returns_existing_registry_row():
    """Removing the unique-registry fallback would create or raise on retry."""
    fingerprint = build_content_fingerprint(
        stem="1 + 1 = ?",
        options=["A. 1", "B. 2"],
        formula_texts=[],
        image_hashes=[],
    )

    first, first_created = reserve_content_fingerprint(fingerprint)
    second, second_created = reserve_content_fingerprint(fingerprint)

    assert first_created is True
    assert second_created is False
    assert second.pk == first.pk
    assert second.state == QuestionContentFingerprint.State.RESERVING
    assert QuestionContentFingerprint.objects.filter(fingerprint=fingerprint).count() == 1


@pytest.mark.django_db
def test_activation_attaches_question_and_marks_registry_active():
    """Omitting either activation update would leave a reserved duplicate lock."""
    paper = ExamPaper.objects.create(
        title="fingerprint test paper",
        subject="math",
        source_file_path="test.pdf",
    )
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no="1",
        question_type="single_choice",
        stem="1 + 1 = ?",
    )
    registry, _ = reserve_content_fingerprint("c" * 64)

    activated = activate_content_fingerprint(registry, question)

    registry.refresh_from_db()
    assert activated.pk == registry.pk
    assert registry.canonical_question == question
    assert registry.state == QuestionContentFingerprint.State.ACTIVE
