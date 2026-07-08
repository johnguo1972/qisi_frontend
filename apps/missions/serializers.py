from rest_framework import serializers
from django.db import models
from .models import LearningMission, MissionLevel, MissionQuestionRel


class MissionListSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator_teacher.display_name', read_only=True)
    level_count = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = LearningMission
        fields = ['id', 'mission_no', 'mission_name', 'goal_text',
                  'status', 'start_at', 'end_at', 'creator_name',
                  'level_count', 'class_name', 'question_count',
                  'default_mode_policy', 'class_obj']

    def get_level_count(self, obj):
        return obj.levels.count()

    def get_class_name(self, obj):
        if obj.class_obj:
            return obj.class_obj.class_name
        return None

    def get_question_count(self, obj):
        return MissionQuestionRel.objects.filter(mission=obj).count()


class MissionDetailSerializer(serializers.ModelSerializer):
    levels = serializers.SerializerMethodField()
    creator_name = serializers.CharField(source='creator_teacher.display_name', read_only=True)
    creator_teacher = serializers.IntegerField(source='creator_teacher_id.id', read_only=True)

    class Meta:
        model = LearningMission
        fields = ['id', 'mission_no', 'mission_name', 'goal_text',
                  'creator_teacher', 'creator_name', 'start_at', 'end_at',
                  'status', 'default_mode_policy', 'levels']

    def get_levels(self, obj):
        levels = obj.levels.all()
        return [{
            'id': lv.id, 'level_no': lv.level_no, 'level_name': lv.level_name,
            'level_type': lv.level_type, 'pass_rule_json': lv.pass_rule_json,
            'mode_policy': lv.mode_policy, 'hint_strength': lv.hint_strength,
            'question_count': MissionQuestionRel.objects.filter(level_id=lv.id).count(),
        } for lv in levels]


class CreateMissionSerializer(serializers.ModelSerializer):
    class_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = LearningMission
        fields = ['mission_name', 'goal_text', 'start_at', 'end_at', 'default_mode_policy', 'class_id']

    def create(self, validated_data):
        class_id = validated_data.pop('class_id', None)
        if class_id:
            from apps.institutions.models import Class
            try:
                validated_data['class_obj'] = Class.objects.get(pk=class_id)
            except Class.DoesNotExist:
                pass
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
    level_id = serializers.IntegerField()
    question_ids = serializers.ListField(child=serializers.IntegerField())
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
