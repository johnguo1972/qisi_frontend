"""Content identities used to de-duplicate imported questions."""
import hashlib
import json
import unicodedata

from django.db import IntegrityError, transaction


def _normalize_text(value):
    """Return the canonical text representation for fingerprint input."""
    text = unicodedata.normalize("NFKC", "" if value is None else str(value))
    return " ".join(text.split())


def build_content_fingerprint(*, stem, options, formula_texts, image_hashes) -> str:
    """Build the content-v1 SHA-256 fingerprint for a parsed question."""
    content = {
        "stem": _normalize_text(stem),
        "options": [_normalize_text(option) for option in options],
        "formula_texts": [_normalize_text(formula) for formula in formula_texts],
        "image_hashes": [_normalize_text(image_hash) for image_hash in image_hashes],
    }
    canonical_json = json.dumps(
        content,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def reserve_content_fingerprint(fingerprint):
    """Create a reservation or return the row already reserved by another writer."""
    from apps.parser.models import QuestionContentFingerprint

    try:
        with transaction.atomic():
            return QuestionContentFingerprint.objects.create(
                fingerprint=fingerprint,
            ), True
    except IntegrityError:
        return QuestionContentFingerprint.objects.get(fingerprint=fingerprint), False


def activate_content_fingerprint(registry, question):
    """Attach a created question to its reservation and make it canonical."""
    from apps.parser.models import QuestionContentFingerprint

    with transaction.atomic():
        locked_registry = QuestionContentFingerprint.objects.select_for_update().get(
            pk=registry.pk
        )
        locked_registry.canonical_question = question
        locked_registry.state = QuestionContentFingerprint.State.ACTIVE
        locked_registry.save(update_fields=("canonical_question", "state"))
    return locked_registry
