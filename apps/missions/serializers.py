from rest_framework import serializers
from django.db import models
from .models import LearningMission, MissionLevel, MissionQuestionRel, MissionClassAssignment
from .services import FLAT_ASSIGNMENT_MODE, ordered_mission_question_rels


# 课程和历史题目数据中同时存在中文名称、英文编码和单字母编码。
# 列表展示统一为中文，筛选保留所有已有编码，避免历史任务无法被筛选。
SUBJECT_ALIASES = {
    '数学': ('数学', 'math', 'M'),
    '物理': ('物理', 'physics', 'P'),
    '化学': ('化学', 'chemistry', 'C'),
    '生物': ('生物', 'biology', 'B'),
    '语文': ('语文', 'chinese', 'CNL'),
    '英语': ('英语', 'english', 'E'),
    '历史': ('历史', 'history', 'H'),
    '地理': ('地理', 'geography', 'G'),
    '道德与法治': ('道德与法治', 'politics', 'morality'),
}
SUBJECT_LABELS = {
    alias.lower(): label
    for label, aliases in SUBJECT_ALIASES.items()
    for alias in aliases
}


def normalize_subject_label(value):
    raw = str(value or '').strip()
    return SUBJECT_LABELS.get(raw.lower(), raw or '未设置')


def subject_filter_values(value):
    """Return all stored values that represent the requested subject."""
    raw = str(value or '').strip()
    label = normalize_subject_label(raw)
    return set(SUBJECT_ALIASES.get(label, (raw,)))


class MissionListSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator_teacher.display_name', read_only=True)
    level_count = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    unfinished_count = serializers.SerializerMethodField()
    completion_progress = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    class_names = serializers.SerializerMethodField()
    class_ids = serializers.SerializerMethodField()

    class Meta:
        model = LearningMission
        fields = ['id', 'mission_no', 'mission_name', 'goal_text',
                  'status', 'start_at', 'end_at', 'creator_name',
                  'assignment_mode', 'mission_kind', 'source_type', 'level_count', 'class_name', 'class_names', 'class_ids', 'question_count', 'unfinished_count', 'completion_progress', 'subject',
                  'default_mode_policy', 'class_obj', 'target_student_ids', 'course',
                  'source_matrix_id', 'source_generation_batch_id', 'parent_mission_id']

    def get_level_count(self, obj):
        return 0 if obj.assignment_mode == FLAT_ASSIGNMENT_MODE else obj.levels.count()

    def get_class_name(self, obj):
        if obj.class_obj:
            return obj.class_obj.class_name
        return None

    def _assignments(self, obj):
        items = list(obj.class_assignments.filter(status='active').select_related('class_obj'))
        return items or ([obj] if obj.class_obj_id else [])

    def get_class_names(self, obj):
        return [item.class_obj.class_name for item in self._assignments(obj) if getattr(item, 'class_obj', None)]

    def get_class_ids(self, obj):
        return [str(item.class_obj_id) for item in self._assignments(obj) if getattr(item, 'class_obj_id', None)]

    def get_question_count(self, obj):
        return MissionQuestionRel.objects.filter(mission=obj).count()

    def get_unfinished_count(self, obj):
        from apps.study.models import StudentMissionProgress
        return StudentMissionProgress.objects.filter(mission=obj).exclude(
            progress_status__in=('completed', 'passed'),
        ).count()

    def get_completion_progress(self, obj):
        """Return the overall completion progress for this assignment."""
        from django.db.models import Q
        from apps.accounts.models import UserAccount
        from apps.institutions.models import ClassStudent
        from apps.study.models import StudentMissionProgress

        targets = {str(student_id) for student_id in (obj.target_student_ids or [])}
        assignments = list(obj.class_assignments.filter(status='active').values_list('class_obj_id', 'target_student_ids'))
        if not assignments and obj.class_obj_id:
            assignments = [(obj.class_obj_id, list(targets))]
        student_id_set = set()
        for class_id, class_targets in assignments:
            assigned_students = ClassStudent.objects.filter(class_obj_id=class_id, status='active')
            effective_targets = {str(value) for value in (class_targets or [])} or targets
            if effective_targets:
                assigned_students = assigned_students.filter(student_id__in=effective_targets)
            student_id_set.update(str(value) for value in assigned_students.values_list('student_id', flat=True))
        student_ids = UserAccount.objects.filter(id__in=student_id_set, status='active').values_list('id', flat=True)

        total = student_ids.count()
        completed = StudentMissionProgress.objects.filter(
            mission=obj,
            student_user_id__in=student_ids,
            progress_status__in=('completed', 'passed'),
        ).count()
        completed = min(completed, total)
        unfinished = max(total - completed, 0)
        percent = round(completed / total * 100, 2) if total else 0
        return {
            'completed': completed,
            'total': total,
            'unfinished': unfinished,
            'percent': percent,
        }

    def get_subject(self, obj):
        if obj.course_id and getattr(obj, 'course', None):
            return normalize_subject_label(obj.course.subject)

        # 兼容没有课程关联的历史任务：从已关联题目的科目中取第一个非空值。
        question_ids = MissionQuestionRel.objects.filter(mission=obj).values_list('question_id', flat=True)
        from apps.parser.models import ExamQuestion
        subject = ExamQuestion.objects.filter(
            id__in=question_ids,
        ).exclude(subject__isnull=True).exclude(subject='').values_list('subject', flat=True).first()
        return normalize_subject_label(subject)


class MissionDetailSerializer(serializers.ModelSerializer):
    levels = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source='creator_teacher.display_name', read_only=True)
    creator_teacher = serializers.UUIDField(source='creator_teacher_id.id', read_only=True)
    class_obj = serializers.UUIDField(source='class_obj_id', read_only=True, allow_null=True)
    question_ids = serializers.SerializerMethodField()
    class_ids = serializers.SerializerMethodField()
    class_names = serializers.SerializerMethodField()

    class Meta:
        model = LearningMission
        fields = ['id', 'mission_no', 'mission_name', 'goal_text',
                  'creator_teacher', 'creator_name', 'start_at', 'end_at',
                  'status', 'assignment_mode', 'default_mode_policy', 'levels',
                  'question_ids', 'class_obj', 'class_ids', 'class_names', 'target_student_ids', 'course', 'mission_kind', 'source_type',
                  'source_matrix_id', 'source_generation_batch_id', 'parent_mission_id']

    def get_levels(self, obj):
        levels = obj.levels.all()
        if obj.assignment_mode == FLAT_ASSIGNMENT_MODE:
            levels = levels.order_by('level_no', 'id')[:1]
        return [{
            'id': lv.id, 'level_no': lv.level_no, 'level_name': lv.level_name,
            'level_type': lv.level_type, 'pass_rule_json': lv.pass_rule_json,
            'mode_policy': lv.mode_policy, 'hint_strength': lv.hint_strength,
            'question_count': MissionQuestionRel.objects.filter(level_id=lv.id).count(),
        } for lv in levels]

    def get_question_ids(self, obj):
        return [rel.question_id for rel in ordered_mission_question_rels(obj)]

    def get_class_ids(self, obj):
        assignments = list(obj.class_assignments.filter(status='active').values_list('class_obj_id', flat=True))
        return [str(value) for value in assignments] or ([str(obj.class_obj_id)] if obj.class_obj_id else [])

    def get_class_names(self, obj):
        return list(obj.class_assignments.filter(status='active').values_list('class_obj__class_name', flat=True)) or ([obj.class_obj.class_name] if obj.class_obj else [])


class CreateMissionSerializer(serializers.ModelSerializer):
    class_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    class_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False, allow_empty=True)
    target_student_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    course_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    mission_kind = serializers.ChoiceField(choices=['regular', 'drill', 'wrongbook_personal'], required=False, default='regular')
    source_type = serializers.ChoiceField(choices=['question_bank', 'handout', 'wrongbook', 'ai_recommendation', 'teacher_matrix'], required=False, default='question_bank')

    class Meta:
        model = LearningMission
        fields = ['mission_name', 'goal_text', 'start_at', 'end_at', 'default_mode_policy', 'class_id', 'class_ids', 'course_id', 'target_student_ids', 'mission_kind', 'source_type']

    def create(self, validated_data):
        class_id = validated_data.pop('class_id', None)
        class_ids = validated_data.pop('class_ids', None)
        course_id = validated_data.pop('course_id', None)
        # JSONField stores target IDs as strings; DRF's UUIDField returns UUID
        # objects, which PostgreSQL's JSON adapter cannot serialize directly.
        validated_data['target_student_ids'] = [
            str(student_id) for student_id in validated_data.get('target_student_ids', [])
        ]
        if not validated_data.get('start_at'):
            from django.utils import timezone
            validated_data['start_at'] = timezone.now()
        validated_data['assignment_mode'] = FLAT_ASSIGNMENT_MODE
        if class_id:
            from apps.institutions.models import Class
            try:
                validated_data['class_obj'] = Class.objects.get(pk=class_id)
            except Class.DoesNotExist:
                pass
        if class_ids is not None:
            # The view performs the same validation for update requests. Keep
            # creation atomic here so no mission can be left half-assigned.
            from django.db import transaction
            from apps.institutions.models import Class, ClassTeacher
            from apps.courses.models import Course
            request = self.context.get('request')
            ids = list(dict.fromkeys(str(value) for value in class_ids if value))
            classes = list(Class.objects.filter(pk__in=ids, status='active'))
            if len(classes) != len(ids):
                raise serializers.ValidationError({'class_ids': '存在无效或已停用的班级'})
            if request and not all(
                ClassTeacher.objects.filter(class_obj=cls, teacher=request.user).exists()
                or cls.creator_teacher_id == request.user.id
                for cls in classes
            ):
                raise serializers.ValidationError({'class_ids': '只能选择自己管理的班级'})
            from .services import class_grade_in_teacher_scope
            if request and any(not class_grade_in_teacher_scope(cls, request.user) for cls in classes):
                raise serializers.ValidationError({'class_ids': '所选班级年级超出教师任教范围'})
            validated_data['class_obj'] = classes[0] if classes else None
            if course_id:
                validated_data['course_id'] = course_id if Course.objects.filter(pk=course_id).exists() else None
            with transaction.atomic():
                mission = super().create(validated_data)
                for cls in classes:
                    MissionClassAssignment.objects.create(
                        mission=mission, class_obj=cls,
                        start_at=mission.start_at, end_at=mission.end_at,
                        target_student_ids=list(mission.target_student_ids or []),
                    )
            return mission
        if course_id:
            from apps.courses.models import Course
            validated_data['course_id'] = course_id if Course.objects.filter(pk=course_id).exists() else None
        return super().create(validated_data)


class CreateLevelSerializer(serializers.ModelSerializer):
    level_no = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = MissionLevel
        fields = ['level_no', 'level_name', 'level_type', 'pass_rule_json',
                  'mode_policy', 'hint_strength']

    def create(self, validated_data):
        # 如果没有提供 level_no，自动计算为当前最大 level_no + 1
        if 'level_no' not in validated_data or validated_data.get('level_no') is None:
            mission = validated_data.get('mission')
            if mission:
                max_no = mission.levels.aggregate(models.Max('level_no'))['level_no__max']
                validated_data['level_no'] = (max_no or 0) + 1
        return super().create(validated_data)


class AddQuestionsSerializer(serializers.Serializer):
    level_id = serializers.UUIDField()
    question_ids = serializers.ListField(child=serializers.UUIDField())
    is_required = serializers.BooleanField(default=True)


class FlatQuestionsSerializer(serializers.Serializer):
    """Replace the flat assignment question list while hiding legacy levels."""
    question_ids = serializers.ListField(
        child=serializers.UUIDField(), allow_empty=False,
    )


class BatchCreateLevelsSerializer(serializers.Serializer):
    """批量创建关卡及分配题目"""
    levels = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )

    def validate(self, data):
        levels = data.get('levels', [])
        for i, lv in enumerate(levels):
            if not lv.get('level_name') and not lv.get('name'):
                raise serializers.ValidationError(f'关卡{i+1}缺少名称')
            if not lv.get('level_type') and not lv.get('type'):
                raise serializers.ValidationError(f'关卡{i+1}缺少类型')
        return data
