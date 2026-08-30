from rest_framework import serializers
from .models import Handout, HandoutQuestion


class HandoutSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source='creator_teacher.display_name', read_only=True)
    question_count = serializers.SerializerMethodField()
    course_name = serializers.CharField(source='course.name', read_only=True)

    class Meta:
        model = Handout
        fields = [
            'id', 'name', 'subject', 'stage', 'grade', 'creator_teacher', 'creator_name',
            'course', 'course_name', 'status', 'version', 'pdf_file_path', 'question_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'creator_teacher', 'creator_name', 'course_name', 'version', 'pdf_file_path', 'question_count', 'created_at', 'updated_at']

    def get_question_count(self, obj):
        return obj.questions.count()


class HandoutQuestionSerializer(serializers.ModelSerializer):
    question_id = serializers.UUIDField(source='question.id', read_only=True)

    class Meta:
        model = HandoutQuestion
        fields = ['id', 'question_id', 'sort_no', 'source_type', 'display_snapshot']
        read_only_fields = fields
