from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import LearningMission, MissionLevel


FLAT_ASSIGNMENT_MODE = 'flat'
LEGACY_ASSIGNMENT_MODE = 'levels'


def close_stale_missions(now=None):
    """Close assignments whose deadline passed more than ten days ago.

    The project does not require a separate scheduler for this business rule;
    callers invoke it before reading or changing assignment state.  The update
    is idempotent and intentionally includes drafts so stale unsent homework
    cannot remain indefinitely in an active list.
    """
    now = now or timezone.now()
    threshold = now - timedelta(days=10)
    return LearningMission.objects.filter(
        status__in=('draft', 'published', 'running'),
        end_at__isnull=False,
        end_at__lt=threshold,
    ).update(status='closed', updated_at=now)


@transaction.atomic
def ensure_flat_assignment_level(mission):
    """Return the hidden compatibility container for a flat assignment."""
    level = mission.levels.order_by('level_no', 'id').first()
    if level is None:
        level = MissionLevel.objects.create(
            mission=mission,
            level_no=1,
            level_name='作业题目',
            level_type='practice',
            mode_policy=mission.default_mode_policy or 'free_practice',
        )
    return level


def assignment_levels(mission):
    """Return visible levels while hiding the compatibility level for flat work."""
    levels = mission.levels.all()
    if getattr(mission, 'assignment_mode', LEGACY_ASSIGNMENT_MODE) == FLAT_ASSIGNMENT_MODE:
        first = levels.order_by('level_no', 'id').first()
        return [first] if first is not None else []
    return levels
