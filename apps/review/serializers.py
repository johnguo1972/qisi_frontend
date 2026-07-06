"""Serializers for review API."""
from rest_framework import serializers
from apps.parser.models import ExamQuestion, QuestionOption, QuestionImage, ExamPage
from apps.papers.models import ExamPaper


class QuestionOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionOption
        fields = ['id', 'option_label', 'content', 'bbox', 'sort_order']


class QuestionImageListSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionImage
        fields = ['id', 'image_type', 'file_path', 'bbox', 'expanded_bbox', 'description']


class QuestionDetailSerializer(serializers.ModelSerializer):
    options = QuestionOptionSerializer(many=True, read_only=True)
    images = QuestionImageListSerializer(many=True, read_only=True)
    pdf_file_path = serializers.CharField(source='paper.pdf_file_path', read_only=True, default='')

    class Meta:
        model = ExamQuestion
        fields = [
            'id', 'question_no', 'section_title', 'question_type', 'subject',
            'paper',  # FK ID for frontend paper_id binding
            'stem', 'stem_html', 'answer', 'analysis', 'solution', 'comment',
            'knowledge_points', 'difficulty', 'page_start', 'page_end',
            'bbox', 'confidence', 'formula_need_review', 'need_review',
            'review_status', 'parse_status', 'sort_order',
            'options', 'images', 'pdf_file_path',
            # AI enrichment fields
            'ai_answer_a', 'ai_answer_b', 'ai_answer_c',
            'ai_knowledge_enrichment', 'ai_probe_result',
            'ai_vision_extract', 'ai_verifier_result',
        ]


class QuestionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating question during review."""
    class Meta:
        model = ExamQuestion
        fields = [
            'stem', 'stem_html', 'answer', 'analysis', 'solution',
            'comment', 'raw_explanation', 'knowledge_points', 'difficulty',
            'question_type', 'review_status', 'page_start', 'page_end',
        ]


class QuestionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for question list view."""
    options_count = serializers.SerializerMethodField()
    images_count = serializers.SerializerMethodField()
    knowledge_points_count = serializers.SerializerMethodField()

    class Meta:
        model = ExamQuestion
        fields = [
            'id', 'question_no', 'question_type', 'stem', 'answer',
            'confidence', 'need_review', 'review_status', 'difficulty',
            'options_count', 'images_count', 'knowledge_points_count',
            # AI enrichment fields (for display in list)
            'ai_answer_a', 'ai_answer_b', 'ai_answer_c',
            'ai_knowledge_enrichment', 'ai_probe_result',
            'ai_vision_extract', 'ai_verifier_result',
        ]

    def get_options_count(self, obj):
        return obj.options.count()

    def get_images_count(self, obj):
        return obj.images.count()

    def get_knowledge_points_count(self, obj):
        kps = obj.knowledge_points
        return len(kps) if isinstance(kps, list) else 0


class PaperReviewSerializer(serializers.ModelSerializer):
    total_questions = serializers.IntegerField(read_only=True)
    pending_review = serializers.SerializerMethodField()

    class Meta:
        model = ExamPaper
        fields = ['id', 'title', 'subject', 'status', 'total_pages', 'total_questions', 'pending_review']

    def get_pending_review(self, obj):
        return ExamQuestion.objects.filter(paper=obj, need_review=True).count()


class AIStatusSerializer(serializers.Serializer):
    """Serializer for AI processing status."""
    question_id = serializers.IntegerField()
    knowledge_points_count = serializers.IntegerField()
    knowledge_enrichment = serializers.JSONField(required=False, allow_null=True)
    answer_a_status = serializers.CharField()
    answer_b_status = serializers.CharField()
    answer_c_status = serializers.CharField()
    answer_a = serializers.JSONField(required=False, allow_null=True)
    answer_b = serializers.JSONField(required=False, allow_null=True)
    answer_c = serializers.JSONField(required=False, allow_null=True)


class AIProcessRequestSerializer(serializers.Serializer):
    """Serializer for AI process request."""
    model = serializers.CharField(required=False, allow_blank=True, max_length=100)


class AIProcessResultSerializer(serializers.Serializer):
    """Serializer for AI processing results."""
    question_id = serializers.IntegerField()
    ai_processing_status = serializers.CharField()
    ai_processed_at = serializers.DateTimeField(read_only=True)
    ai_probe_result = serializers.JSONField(read_only=True)
    ai_vision_extract = serializers.JSONField(read_only=True)
    ai_verifier_result = serializers.JSONField(read_only=True)
    ai_answer_a = serializers.JSONField(read_only=True)
    ai_answer_b = serializers.JSONField(read_only=True)
    ai_answer_c = serializers.JSONField(read_only=True)
