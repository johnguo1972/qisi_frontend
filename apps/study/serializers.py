"""Serializers for study app (question search, import, dicts)."""
from rest_framework import serializers
from apps.parser.models import ExamQuestion
from apps.papers.models import ParseTask, ExamPaper


class QuestionListSerializer(serializers.ModelSerializer):
    knowledge_points_count = serializers.SerializerMethodField()
    stem_preview = serializers.SerializerMethodField()
    ai_answer_a = serializers.SerializerMethodField()
    ai_answer_b = serializers.SerializerMethodField()
    ai_answer_c = serializers.SerializerMethodField()
    ai_answer_a_confirmed = serializers.SerializerMethodField()
    ai_answer_b_confirmed = serializers.SerializerMethodField()
    ai_answer_c_confirmed = serializers.SerializerMethodField()
    paper_title = serializers.CharField(source='paper.title', read_only=True, default='')

    class Meta:
        model = ExamQuestion
        fields = ['id', 'question_no', 'system_id', 'question_type', 'difficulty',
                  'subject', 'review_status', 'stem_preview', 'knowledge_points_count',
                  'ai_answer_a', 'ai_answer_b', 'ai_answer_c',
                  'ai_answer_a_confirmed', 'ai_answer_b_confirmed', 'ai_answer_c_confirmed',
                  'paper_title']

    def get_stem_preview(self, obj):
        stem = obj.stem or ''
        return (stem[:80] + '...') if len(stem) > 80 else stem

    def get_knowledge_points_count(self, obj):
        if obj.ai_knowledge_enrichment:
            return len(obj.ai_knowledge_enrichment.get('points', []))
        if obj.knowledge_points:
            return len(obj.knowledge_points) if isinstance(obj.knowledge_points, list) else 0
        return 0

    def get_ai_answer_a(self, obj):
        return obj.ai_answer_a

    def get_ai_answer_b(self, obj):
        return obj.ai_answer_b

    def get_ai_answer_c(self, obj):
        return obj.ai_answer_c

    def _has_answer(self, data):
        """Return True if the AI answer exists and is non-empty."""
        if not data:
            return False
        if isinstance(data, dict):
            return bool(data)
        if isinstance(data, list):
            return len(data) > 0
        return bool(data)

    def get_ai_answer_a_confirmed(self, obj):
        return self._has_answer(obj.ai_answer_a)

    def get_ai_answer_b_confirmed(self, obj):
        return self._has_answer(obj.ai_answer_b)

    def get_ai_answer_c_confirmed(self, obj):
        return self._has_answer(obj.ai_answer_c)


class QuestionDetailSerializer(serializers.ModelSerializer):
    ai_answer_a = serializers.JSONField(required=False)
    ai_answer_b = serializers.JSONField(required=False)
    ai_answer_c = serializers.JSONField(required=False)

    class Meta:
        model = ExamQuestion
        fields = ['id', 'paper', 'question_no', 'system_id', 'paper_question_no',
                  'parent_question', 'section_title', 'question_type', 'subject',
                  'stem', 'stem_html', 'answer', 'analysis', 'solution',
                  'comment', 'raw_explanation', 'raw_text',
                  'knowledge_points', 'difficulty', 'original_question',
                  'page_start', 'page_end', 'bbox', 'region_json',
                  'sort_order', 'confidence', 'formula_need_review',
                  'need_review', 'review_status', 'parse_status',
                  'ai_answer_a', 'ai_answer_b', 'ai_answer_c',
                  'ai_knowledge_enrichment', 'created_at', 'updated_at']


class ImportBatchSerializer(serializers.ModelSerializer):
    paper_title = serializers.CharField(source='paper.title', read_only=True)
    paper_subject = serializers.CharField(source='paper.subject', read_only=True)

    class Meta:
        model = ParseTask
        fields = ['id', 'paper', 'paper_title', 'paper_subject', 'task_type',
                  'status', 'progress', 'current_step', 'created_at', 'finished_at']


class PaperListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamPaper
        fields = ['id', 'title', 'paper_code', 'subject', 'grade',
                  'total_questions', 'status', 'created_at']
