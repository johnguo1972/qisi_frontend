from rest_framework import serializers
from .models import WrongBookItem, MasteryRecord
from apps.common.media import media_url
from apps.common.question_display import difficulty_label
from apps.common.subject_codes import SUBJECT_LABELS, normalize_subject_code


LEGACY_SUBJECT_CODES = {
    'm': 'math', 'p': 'physics', 'c': 'chemistry', 'e': 'english',
    'cnl': 'chinese', 'b': 'biology', 'g': 'geography', 'h': 'history',
}


def _canonical_subject(value):
    raw = str(value or '').strip()
    return normalize_subject_code(raw) or LEGACY_SUBJECT_CODES.get(raw.lower(), '')


class WrongBookItemSerializer(serializers.ModelSerializer):
    question_no = serializers.SerializerMethodField()
    question_type = serializers.SerializerMethodField()
    question_type_label = serializers.SerializerMethodField()
    difficulty = serializers.SerializerMethodField()
    difficulty_label = serializers.SerializerMethodField()
    knowledge_point_labels = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    stem = serializers.SerializerMethodField()
    stem_html = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    subject_label = serializers.SerializerMethodField()

    class Meta:
        model = WrongBookItem
        fields = ['id', 'question_id', 'question_no', 'question_type', 'question_type_label',
                  'difficulty', 'difficulty_label', 'knowledge_point_labels', 'tags',
                  'subject', 'subject_label',
                  'stem', 'stem_html', 'images',
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

    def get_question_type_label(self, obj):
        q = self._get_question(obj)
        return q.get_question_type_display_label() if q else ''

    def get_difficulty(self, obj):
        q = self._get_question(obj)
        return float(q.difficulty) if q and q.difficulty is not None else None

    def get_difficulty_label(self, obj):
        q = self._get_question(obj)
        return difficulty_label(q.difficulty if q else None)

    def get_subject(self, obj):
        q = self._get_question(obj)
        if not q:
            return ''
        return _canonical_subject(q.subject or (q.paper.subject if q.paper else ''))

    def get_subject_label(self, obj):
        code = self.get_subject(obj)
        return SUBJECT_LABELS.get(code, code or '未设置科目')

    def get_knowledge_point_labels(self, obj):
        q = self._get_question(obj)
        if not q:
            return []
        raw = q.knowledge_points
        if not raw and isinstance(q.ai_knowledge_enrichment, dict):
            raw = q.ai_knowledge_enrichment.get('knowledge_points')
        if isinstance(raw, dict):
            raw = raw.get('points') or raw.get('knowledge_points') or []
        if not isinstance(raw, (list, tuple)):
            raw = [raw] if raw else []
        labels = []
        for item in raw:
            if isinstance(item, dict):
                label = item.get('module') or item.get('name') or item.get('label') or item.get('id')
            else:
                label = item
            label = str(label).strip() if label is not None else ''
            if label and label not in labels:
                labels.append(label)
        return labels

    def get_tags(self, obj):
        q = self._get_question(obj)
        raw = q.tags if q else []
        values = raw if isinstance(raw, (list, tuple)) else ([raw] if raw else [])
        result = []
        for value in values:
            text = str(value).strip()
            if text and text not in result:
                result.append(text)
        return result

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
