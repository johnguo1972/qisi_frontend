"""课程管理模块序列化器"""
from rest_framework import serializers
from .models import Course, CourseMaterial, CourseTree, VariantTask


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
            'material_count', 'question_count', 'class_count',
            'is_deleted', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'teacher', 'created_at', 'updated_at']

    def get_material_count(self, obj):
        return obj.materials.filter(is_deleted=False).count()

    def get_question_count(self, obj):
        return obj.question_links.filter(is_deleted=False).count()

    def get_class_count(self, obj):
        return obj.tree_nodes.count()

    def create(self, validated_data):
        validated_data['teacher'] = self.context['request'].user
        return super().create(validated_data)


class CourseMaterialSerializer(serializers.ModelSerializer):
    """课程资料序列化器"""
    uploaded_by_name = serializers.CharField(source='uploaded_by.display_name', read_only=True)

    class Meta:
        model = CourseMaterial
        fields = [
            'id', 'course', 'name', 'file_path', 'file_type',
            'file_size', 'mime_type', 'uploaded_by', 'uploaded_by_name',
            'is_deleted', 'created_at',
        ]
        read_only_fields = ['id', 'course', 'uploaded_by', 'created_at']


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
        read_only_fields = ['id', 'course', 'created_at']

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
