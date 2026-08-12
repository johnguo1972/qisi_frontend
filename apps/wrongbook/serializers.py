from rest_framework import serializers
from .models import WrongBookItem, MasteryRecord
from apps.common.media import media_url


class WrongBookItemSerializer(serializers.ModelSerializer):
    question_no = serializers.SerializerMethodField()
    question_type = serializers.SerializerMethodField()
    stem = serializers.SerializerMethodField()
    stem_html = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = WrongBookItem
        fields = ['id', 'question_id', 'question_no', 'question_type', 'stem', 'stem_html', 'images',
                  'status', 'wrong_reason_type', 'retry_count',
                  'variant_done_count', 'first_wrong_at', 'latest_wrong_at']

    def _get_question(self, obj):
        if not hasattr(self, '_question_cache'):
            self._question_cache = {}
        key = str(obj.question_id)
        if key not in self._question_cache:
            try:
                from apps.parser.models import ExamQuestion
                self._question_cache[key] = ExamQuestion.objects.get(pk=obj.question_id)
            except Exception:
                self._question_cache[key] = None
        return self._question_cache[key]

    def get_question_no(self, obj):
        q = self._get_question(obj)
        return q.question_no if q else ''

    def get_question_type(self, obj):
        q = self._get_question(obj)
        return q.question_type if q else ''

    def get_stem(self, obj):
        q = self._get_question(obj)
        return q.stem if q else ''

    def get_stem_html(self, obj):
        q = self._get_question(obj)
        return q.stem_html if q else ''

    def get_images(self, obj):
        q = self._get_question(obj)
        if not q:
            return []
        return [
            {
                'id': image.id,
                'url': media_url(image.file_path),
                'file_path': image.file_path,
                'display_width': image.display_width,
            }
            for image in q.images.all().order_by('sort_order')
            if image.file_path and image.image_type != 'formula'
        ]


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
