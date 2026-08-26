"""Canonical subject codes shared by accounts, courses and institutions.

The database and API use the code values.  Chinese labels are presentation
values and are accepted only as a backwards-compatible input alias while old
clients/data are being migrated.
"""

SUBJECT_LABELS = {
    'chinese': '语文',
    'math': '数学',
    'english': '英语',
    'physics': '物理',
    'chemistry': '化学',
    'biology': '生物',
    'geography': '地理',
    'history': '历史',
}

SUBJECT_ALIASES = {
    **{code: code for code in SUBJECT_LABELS},
    **{label: code for code, label in SUBJECT_LABELS.items()},
}


def normalize_subject_code(value):
    """Return the canonical English code or ``None`` for an unknown value."""
    if value is None:
        return None
    return SUBJECT_ALIASES.get(str(value).strip().lower())


def normalize_subject_codes(value):
    """Normalize a scalar/list of subject values without duplicates."""
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        code = normalize_subject_code(item)
        if code and code not in result:
            result.append(code)
    return result
