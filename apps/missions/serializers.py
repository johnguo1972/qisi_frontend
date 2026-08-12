from rest_framework import serializers
from django.db import models
from .models import LearningMission, MissionLevel, MissionQuestionRel


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
    subject = serializers.SerializerMethodField()

    class Meta:
        model = LearningMission
        fields = ['id', 'mission_no', 'mission_name', 'goal_text',
                  'status', 'start_at', 'end_at', 'creator_name',
                  'level_count', 'class_name', 'question_count', 'subject',
                  'default_mode_policy', 'class_obj', 'target_student_ids', 'course']

    def get_level_count(self, obj):
        return obj.levels.count()

    def get_class_name(self, obj):
        if obj.class_obj:
            return obj.class_obj.class_name
        return None

    def get_question_count(self, obj):
        return MissionQuestionRel.objects.filter(mission=obj).count()

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

    class Meta:
        model = LearningMission
        fields = ['id', 'mission_no', 'mission_name', 'goal_text',
                  'creator_teacher', 'creator_name', 'start_at', 'end_at',
                  'status', 'default_mode_policy', 'levels', 'class_obj', 'target_student_ids', 'course']

    def get_levels(self, obj):
        levels = obj.levels.all()
        return [{
            'id': lv.id, 'level_no': lv.level_no, 'level_name': lv.level_name,
            'level_type': lv.level_type, 'pass_rule_json': lv.pass_rule_json,
            'mode_policy': lv.mode_policy, 'hint_strength': lv.hint_strength,
            'question_count': MissionQuestionRel.objects.filter(level_id=lv.id).count(),
        } for lv in levels]


class CreateMissionSerializer(serializers.ModelSerializer):
    class_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    target_student_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    course_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = LearningMission
        fields = ['mission_name', 'goal_text', 'start_at', 'end_at', 'default_mode_policy', 'class_id', 'course_id', 'target_student_ids']

    def create(self, validated_data):
        class_id = validated_data.pop('class_id', None)
        course_id = validated_data.pop('course_id', None)
        # JSONField stores target IDs as strings; DRF's UUIDField returns UUID
        # objects, which PostgreSQL's JSON adapter cannot serialize directly.
        validated_data['target_student_ids'] = [
            str(student_id) for student_id in validated_data.get('target_student_ids', [])
        ]
        if class_id:
            from apps.institutions.models import Class
            try:
                validated_data['class_obj'] = Class.objects.get(pk=class_id)
            except Class.DoesNotExist:
                pass
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
