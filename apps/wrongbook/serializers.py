from rest_framework import serializers
from .models import WrongBookItem, MasteryRecord


class WrongBookItemSerializer(serializers.ModelSerializer):
    question_no = serializers.SerializerMethodField()
    question_type = serializers.SerializerMethodField()

    class Meta:
        model = WrongBookItem
        fields = ['id', 'question_id', 'question_no', 'question_type',
                  'status', 'wrong_reason_type', 'retry_count',
                  'variant_done_count', 'first_wrong_at', 'latest_wrong_at']

    def get_question_no(self, obj):
        try:
            from apps.parser.models import ExamQuestion
            q = ExamQuestion.objects.get(pk=obj.question_id)
            return q.question_no
        except Exception:
            return ''

    def get_question_type(self, obj):
        try:
            from apps.parser.models import ExamQuestion
            q = ExamQuestion.objects.get(pk=obj.question_id)
            return q.question_type
        except Exception:
            return ''


class WrongBookDetailSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()

    class Meta:
        model = WrongBookItem
        fields = ['id', 'question', 'status', 'wrong_reason_type',
                  'retry_count', 'variant_done_count', 'first_wrong_at', 'latest_wrong_at']

    def get_question(self, obj):
        try:
            from apps.parser.models import ExamQuestion
            q = ExamQuestion.objects.get(pk=obj.question_id)
            return {
                'id': q.id,
                'question_no': q.question_no,
                'question_type': q.question_type,
                'difficulty': float(q.difficulty) if q.difficulty else None,
            }
        except Exception:
            return None


class MasteryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = MasteryRecord
        fields = ['id', 'mastery_type', 'target_code', 'mastery_status',
                  'mastery_score', 'next_review_at', 'updated_at']
