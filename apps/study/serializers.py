"""Serializers for study app (question search, import, dicts)."""
from rest_framework import serializers
from apps.parser.models import ExamQuestion
from apps.papers.models import ParseTask, ExamPaper
from apps.knowledge.models import KnowledgePoint
from apps.common.media import media_url


class QuestionListSerializer(serializers.ModelSerializer):
    knowledge_points_count = serializers.SerializerMethodField()
    knowledge_points_display = serializers.SerializerMethodField()
    stem_preview = serializers.SerializerMethodField()
    ai_answer_a = serializers.SerializerMethodField()
    ai_answer_b = serializers.SerializerMethodField()
    ai_answer_c = serializers.SerializerMethodField()
    ai_answer_a_confirmed = serializers.SerializerMethodField()
    ai_answer_b_confirmed = serializers.SerializerMethodField()
    ai_answer_c_confirmed = serializers.SerializerMethodField()
    paper_title = serializers.CharField(source='paper.title', read_only=True, default='')

    # 新增字段：图片列表（最多5张）
    images = serializers.SerializerMethodField()
    # 新增字段：选项列表
    options = serializers.SerializerMethodField()
    # 新增字段：自定义标签
    tags = serializers.JSONField(required=False, default=list)
    # 新增字段：来源题集
    source_collection = serializers.CharField(required=False, default='')
    # 新增字段：创建者姓名
    creator_name = serializers.CharField(required=False, default='')
    # 新增字段：收录日期
    collected_at = serializers.DateTimeField(required=False, read_only=True)

    class Meta:
        model = ExamQuestion
        fields = ['id', 'question_no', 'system_id', 'question_type', 'difficulty',
                  'subject', 'review_status', 'stem', 'stem_preview', 'answer', 'analysis', 'solution',
                  'knowledge_points_count', 'knowledge_points_display',
                  'ai_answer_a', 'ai_answer_b', 'ai_answer_c',
                  'ai_answer_a_confirmed', 'ai_answer_b_confirmed', 'ai_answer_c_confirmed',
                  'paper_title',
                  # 新增字段
                  'images', 'options', 'tags', 'source_collection',
                  'creator_name', 'collected_at',
                  ]

    def get_stem_preview(self, obj):
        stem = obj.stem or ''
        return (stem[:80] + '...') if len(stem) > 80 else stem

    def get_knowledge_points_count(self, obj):
        raw = obj.ai_knowledge_enrichment or obj.knowledge_points or []
        if isinstance(raw, dict):
            raw = raw.get('points') or raw.get('knowledge_points') or []
        if not isinstance(raw, list):
            return 0
        keys = set()
        for item in raw:
            if isinstance(item, dict):
                key = item.get('id') or item.get('code') or item.get('module') or item.get('name')
            else:
                key = item
            if key is not None and str(key):
                keys.add(str(key))
        return len(keys)

    def get_knowledge_points_display(self, obj):
        raw = obj.knowledge_points or obj.ai_knowledge_enrichment or []
        if isinstance(raw, dict):
            raw = raw.get('points') or raw.get('knowledge_points') or []
        if not isinstance(raw, list):
            return []
        modules = [x.get('module') for x in raw if isinstance(x, dict) and x.get('module')]
        ids = [str(x.get('id')) for x in raw if isinstance(x, dict) and x.get('id') is not None]
        points = list(KnowledgePoint.objects.filter(id__in=ids)) if ids else []
        by_id = {str(p.id): p for p in points}
        module_qs = KnowledgePoint.objects.filter(subject=obj.subject, module__in=modules)
        if not module_qs.exists():
            module_qs = KnowledgePoint.objects.filter(module__in=modules)
        for p in module_qs:
            by_id.setdefault(str(p.id), p)
        result, seen = [], set()
        for item in raw:
            module = item.get('module') if isinstance(item, dict) else None
            key = str(item.get('id')) if isinstance(item, dict) and item.get('id') is not None else None
            point = by_id.get(key)
            if point is None and module:
                point = next((p for p in by_id.values() if p.module == module), None)
            name = point.module if point else module
            if name and name not in seen:
                result.append({'id': str(point.id) if point else key, 'name': name})
                seen.add(name)
        return result

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

    # 新增方法：获取图片列表
    def get_images(self, obj):
        return [
            {
                'id': str(img.id),
                'file_path': img.file_path,
                'url': media_url(img.file_path),
                'description': img.description or '',
                'image_type': img.image_type,
                'display_width': img.display_width,
            }
            for img in obj.images.filter(image_type='diagram').order_by('sort_order')[:5]  # 仅返回题目插图，排除公式裁剪图
        ]

    # 新增方法：获取选项列表
    def get_options(self, obj):
        return [
            {
                'label': opt.option_label,
                'content': opt.content,
            }
            for opt in obj.options.all()
        ]


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
                  'ai_knowledge_enrichment', 'tags', 'created_at', 'updated_at']


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
