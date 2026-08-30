from datetime import timedelta
import re

from django.db import transaction
from django.utils import timezone

from .models import LearningMission, MissionLevel, MissionQuestionRel


def question_no_sort_key(value):
    """Return a natural-sort key for question numbers (1, 2, 10, 10.1...)."""
    text = str(value or '').strip()
    tokens = re.findall(r'\d+|[^\d]+', text)
    if not tokens:
        return ((1, ''),)
    return tuple(
        (0, int(token)) if token.isdigit() else (1, token.strip().lower())
        for token in tokens
    )


def ordered_mission_question_rels(mission):
    """Load mission relations in the same natural question-number order everywhere."""
    from apps.parser.models import ExamQuestion

    relations = list(MissionQuestionRel.objects.filter(mission=mission).order_by('sort_no', 'id'))
    question_map = {
        str(row['id']): row['question_no']
        for row in ExamQuestion.objects.filter(id__in=[rel.question_id for rel in relations]).values('id', 'question_no')
    }
    return sorted(
        relations,
        key=lambda rel: (question_no_sort_key(question_map.get(str(rel.question_id), '')), rel.sort_no, str(rel.id)),
    )


def normalize_mission_question_order(mission):
    """Persist natural order for an existing mission and return its relations."""
    relations = ordered_mission_question_rels(mission)
    changed = []
    for sort_no, relation in enumerate(relations, start=1):
        if relation.sort_no != sort_no:
            relation.sort_no = sort_no
            changed.append(relation)
    if changed:
        MissionQuestionRel.objects.bulk_update(changed, ['sort_no'])
    return relations


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


STAGE_GRADES = {
    'primary': {'一年级', '二年级', '三年级', '四年级', '五年级', '六年级'},
    'junior': {'七年级', '八年级', '九年级'},
    'senior': {'高一', '高二', '高三'},
}


def normalize_teacher_stage(value):
    return {
        'primary': 'primary', '小学': 'primary',
        'junior': 'junior', '初中': 'junior',
        'senior': 'senior', '高中': 'senior',
    }.get(str(value or '').strip(), '')


def class_grade_in_teacher_scope(class_obj, teacher):
    """Return whether a class's optional grade is within the teacher scope.

    Blank grades are retained as a legacy-compatible state and cannot be
    checked until the teacher or administrator fills them in.
    """
    grade = str(getattr(class_obj, 'grade_level', '') or '').strip()
    if not grade:
        return True
    stages = {
        normalize_teacher_stage(value)
        for value in (getattr(teacher, 'stages', None) or [])
    }
    return any(grade in STAGE_GRADES.get(stage, set()) for stage in stages)


def mission_visible_to_student(mission, student_id, class_ids=None):
    """Check class membership and mission/assignment target restrictions."""
    student_id = str(student_id)
    allowed_class_ids = None if class_ids is None else {str(value) for value in class_ids}
    assignments = list(
        mission.class_assignments.filter(status='active').values(
            'class_obj_id', 'target_student_ids',
        )
    )
    global_targets = {str(value) for value in (mission.target_student_ids or [])}
    if assignments:
        for assignment in assignments:
            class_id = str(assignment['class_obj_id'])
            if allowed_class_ids is not None and class_id not in allowed_class_ids:
                continue
            targets = {
                str(value) for value in (assignment['target_student_ids'] or [])
            } or global_targets
            if not targets or student_id in targets:
                return True
        return False
    if mission.class_obj_id and allowed_class_ids is not None:
        if str(mission.class_obj_id) not in allowed_class_ids:
            return False
    return not global_targets or student_id in global_targets
