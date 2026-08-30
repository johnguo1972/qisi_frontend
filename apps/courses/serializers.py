"""课程管理模块序列化器"""
from rest_framework import serializers
from .models import Course, CourseMaterial, CourseTree, CourseQuestionLink, VariantTask
from apps.common.media import media_url
from apps.common.question_display import difficulty_label, normalize_tables, preview_text
from apps.common.subject_codes import normalize_subject_code


class CourseSerializer(serializers.ModelSerializer):
    """课程序列化器，包含统计字段"""
    teacher_name = serializers.CharField(source='teacher.display_name', read_only=True)
    material_count = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    class_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'name', 'description', 'subject', 'grade_level',
            'cover_image', 'teacher', 'teacher_name',
            'institution',
            'material_count', 'question_count', 'class_count',
            'is_deleted', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'teacher', 'institution', 'created_at', 'updated_at']

    def validate_subject(self, value):
        normalized = normalize_subject_code(value)
        if not normalized:
            raise serializers.ValidationError('学科必须使用受支持的英文编码')
        return normalized

    def get_material_count(self, obj):
        return obj.materials.filter(is_deleted=False).count()

    def get_question_count(self, obj):
        return obj.question_links.filter(is_deleted=False).count()

    def get_class_count(self, obj):
        return obj.class_relations.filter(status='active').count()

    def create(self, validated_data):
        validated_data['teacher'] = self.context['request'].user
        institution = self.context.get('course_institution')
        if institution is not None:
            validated_data['institution'] = institution
        return super().create(validated_data)


class CourseMaterialSerializer(serializers.ModelSerializer):
    """课程资料序列化器"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.display_name', read_only=True)

    class Meta:
        model = CourseMaterial
        fields = [
            'id', 'course', 'name', 'file_path', 'file_type',
            'file_size', 'mime_type', 'uploaded_by', 'uploaded_by_name',
            'conversion_status', 'converted_pdf_path',
            'is_deleted', 'created_at',
        ]
        read_only_fields = [
            'id', 'course', 'uploaded_by', 'conversion_status',
            'converted_pdf_path', 'created_at',
        ]


class CourseTreeNestedSerializer(serializers.ModelSerializer):
    """课程树嵌套序列化器（递归 children）"""
    children = serializers.SerializerMethodField()

    class Meta:
        model = CourseTree
        fields = ['id', 'course', 'parent', 'name', 'sort_order', 'children', 'created_at']
        read_only_fields = ['id', 'course', 'created_at']

    def get_children(self, obj):
        children = obj.children.all().order_by('sort_order')
        return CourseTreeNestedSerializer(children, many=True, context=self.context).data


class CourseTreeSerializer(serializers.ModelSerializer):
    """课程树扁平节点序列化器"""
    has_children = serializers.SerializerMethodField()

    class Meta:
        model = CourseTree
        fields = ['id', 'course', 'parent', 'name', 'sort_order', 'has_children', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_has_children(self, obj):
        return obj.children.exists()


class VariantTaskSerializer(serializers.ModelSerializer):
    """变式任务序列化器（只读）"""
    class Meta:
        model = VariantTask
        fields = [
            'id', 'original_question', 'variant_mode', 'status',
            'generator_result', 'verifier_result', 'generated_question',
            'error_message', 'created_at', 'completed_at',
        ]
        read_only_fields = fields


class CourseQuestionLinkSerializer(serializers.ModelSerializer):
    """课程习题关联序列化器，包含题目详情"""
    question_id = serializers.UUIDField(source='question.id', read_only=True)
    system_id = serializers.CharField(source='question.system_id', read_only=True)
    question_no = serializers.CharField(source='question.question_no', read_only=True)
    question_type = serializers.CharField(source='question.question_type', read_only=True)
    stem_preview = serializers.SerializerMethodField(read_only=True)
    difficulty = serializers.DecimalField(source='question.difficulty', max_digits=4, decimal_places=2, read_only=True)
    difficulty_label = serializers.SerializerMethodField()
    knowledge_points_count = serializers.SerializerMethodField(read_only=True)
    review_status = serializers.CharField(source='question.review_status', read_only=True)
    ai_answer_a = serializers.JSONField(source='question.ai_answer_a', read_only=True)
    ai_answer_b = serializers.JSONField(source='question.ai_answer_b', read_only=True)
    ai_answer_c = serializers.JSONField(source='question.ai_answer_c', read_only=True)
    source = serializers.CharField(read_only=True)
    tree_node_id = serializers.UUIDField(read_only=True, allow_null=True)
    material = serializers.CharField(source='question.material', read_only=True)
    subquestions = serializers.JSONField(source='question.subquestions', read_only=True)
    tables = serializers.SerializerMethodField()
    options = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = CourseQuestionLink
        fields = [
            'id', 'question_id', 'system_id', 'question_no', 'question_type',
            'stem_preview', 'difficulty', 'difficulty_label', 'knowledge_points_count',
            'review_status', 'ai_answer_a', 'ai_answer_b', 'ai_answer_c',
            'source', 'tree_node_id', 'created_at',
            'material', 'subquestions', 'tables', 'options', 'images',
        ]
        read_only_fields = fields

    def get_stem_preview(self, obj):
        """截取题干前200字符作为预览"""
        return preview_text(
            obj.question.stem,
            obj.question.subquestions,
            obj.question.tables,
            limit=240,
        )

    def get_difficulty_label(self, obj):
        return difficulty_label(obj.question.difficulty)

    def get_tables(self, obj):
        return normalize_tables(obj.question.tables)

    def get_knowledge_points_count(self, obj):
        """知识点数量"""
        kp = obj.question.knowledge_points
        if isinstance(kp, (list, tuple)):
            return len(kp)
        return 0

    def get_options(self, obj):
        return [
            {'label': option.option_label, 'content': option.content}
            for option in obj.question.options.order_by('sort_order', 'id')
        ]

    def get_images(self, obj):
        return [
            {
                'id': str(image.id),
                'file_path': image.file_path,
                'url': media_url(image.file_path),
                'image_type': image.image_type,
                'description': image.description or '',
                'display_width': image.display_width,
            }
            for image in obj.question.images.order_by('image_type', 'sort_order', 'id')
        ]
