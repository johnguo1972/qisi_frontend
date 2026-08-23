"""Shared teacher teaching-scope resolution for knowledge and question APIs."""
from dataclasses import dataclass

from django.db.models import Q

from apps.accounts.auth import get_request_role
from apps.accounts.serializers import normalize_teacher_subjects


SUBJECT_ALIASES = {
    'math': 'math',
    'physics': 'physics',
    'chinese': 'chinese',
    'english': 'english',
    'chemistry': 'chemistry',
    '数学': 'math',
    '物理': 'physics',
    '语文': 'chinese',
    '英语': 'english',
    '化学': 'chemistry',
}

STAGE_ALIASES = {
    'primary': 'primary',
    'junior': 'junior',
    'senior': 'senior',
    '小学': 'primary',
    '初中': 'junior',
    '高中': 'senior',
}

STAGE_DISPLAY = {
    'primary': '小学',
    'junior': '初中',
    'senior': '高中',
}


class TeachingScopeForbidden(Exception):
    """Raised when an active teacher requests data outside teaching scope."""


@dataclass(frozen=True)
class TeacherQuestionScope:
    subjects: tuple[str, ...]
    stages: tuple[str, ...]
    selected_subject: str | None
    configured: bool


def normalize_subject_code(value: object) -> str:
    return SUBJECT_ALIASES.get(str(value or '').strip(), '')


def normalize_stage_codes(value: object) -> tuple[str, ...]:
    raw_values = value.split(',') if isinstance(value, str) else value
    if not isinstance(raw_values, (list, tuple)):
        return ()
    normalized = []
    for raw in raw_values:
        stage = STAGE_ALIASES.get(str(raw or '').strip(), '')
        if stage and stage not in normalized:
            normalized.append(stage)
    return tuple(normalized)


def resolve_teacher_question_scope(
    request,
    requested_subject: str = '',
    requested_stages: object = '',
) -> TeacherQuestionScope | None:
    """Return the active teacher's bounded scope, or None for non-teacher roles."""
    if get_request_role(request) != 'teacher':
        return None

    subjects = []
    for raw_subject in normalize_teacher_subjects(request.user):
        subject = normalize_subject_code(raw_subject)
        if subject and subject not in subjects:
            subjects.append(subject)
    stages = normalize_stage_codes(getattr(request.user, 'stages', None))
    if not subjects or not stages:
        return TeacherQuestionScope(tuple(subjects), stages, None, False)

    selected_subject = normalize_subject_code(requested_subject)
    if requested_subject and not selected_subject:
        raise TeachingScopeForbidden('subject')
    if selected_subject and selected_subject not in subjects:
        raise TeachingScopeForbidden('subject')
    selected_subject = selected_subject or subjects[0]

    requested_stage_codes = normalize_stage_codes(requested_stages)
    if requested_stages and not requested_stage_codes:
        raise TeachingScopeForbidden('stages')
    if any(stage not in stages for stage in requested_stage_codes):
        raise TeachingScopeForbidden('stages')

    return TeacherQuestionScope(
        tuple(subjects),
        stages,
        selected_subject,
        True,
    )


def apply_stage_scope(queryset, stages: tuple[str, ...]):
    """Filter paper-backed questions to a teacher's configured school stages."""
    if not stages:
        return queryset.none()

    stage_query = Q()
    for stage in stages:
        display = STAGE_DISPLAY[stage]
        stage_query |= (
            Q(paper__stage__icontains=display)
            | Q(paper__grade__icontains=display)
            | Q(paper__stage__icontains=stage)
            | Q(paper__grade__icontains=stage)
        )
    return queryset.filter(stage_query)
