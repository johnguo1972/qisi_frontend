"""课程管理模块数据模型"""
from django.db import models
from django.conf import settings


class Course(models.Model):
    """课程"""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=200, verbose_name='课程名称')
    description = models.TextField(null=True, blank=True, verbose_name='课程描述')
    subject = models.CharField(max_length=50, verbose_name='学科')
    grade_level = models.CharField(max_length=50, verbose_name='年级')
    cover_image = models.CharField(max_length=500, null=True, blank=True, verbose_name='封面图片')
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='courses',
        db_column='teacher_id',
        verbose_name='教师',
    )
    is_deleted = models.BooleanField(default=False, verbose_name='软删除标记')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'course'
        verbose_name = '课程'
        verbose_name_plural = '课程'

    def __str__(self):
        return f'{self.name} ({self.subject})'


class CourseMaterial(models.Model):
    """课程资料"""
    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='materials',
        db_column='course_id',
        verbose_name='课程',
    )
    name = models.CharField(max_length=255, verbose_name='资料名称')
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    file_type = models.CharField(max_length=20, verbose_name='文件类型')
    file_size = models.BigIntegerField(verbose_name='文件大小(字节)')
    mime_type = models.CharField(max_length=100, verbose_name='MIME类型')
    is_deleted = models.BooleanField(default=False, verbose_name='软删除标记')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_materials',
        db_column='uploaded_by_id',
        verbose_name='上传者',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_material'
        verbose_name = '课程资料'
        verbose_name_plural = '课程资料'

    def __str__(self):
        return f'{self.name} ({self.file_type})'


class CourseTree(models.Model):
    """课程树结构节点"""
    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='tree_nodes',
        db_column='course_id',
        verbose_name='课程',
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        db_column='parent_id',
        verbose_name='父节点',
    )
    name = models.CharField(max_length=200, verbose_name='节点名称')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_tree'
        verbose_name = '课程树节点'
        verbose_name_plural = '课程树节点'
        ordering = ['sort_order']

    def __str__(self):
        return f'{self.name}'


class CourseQuestionLink(models.Model):
    """课程习题关联"""
    SOURCE_CHOICES = [
        ('manual', '手动添加'),
        ('import', '导入'),
        ('generated', '生成'),
    ]

    id = models.BigAutoField(primary_key=True)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='question_links',
        db_column='course_id',
        verbose_name='课程',
    )
    tree_node = models.ForeignKey(
        CourseTree,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='question_links',
        db_column='tree_node_id',
        verbose_name='树节点',
    )
    question = models.ForeignKey(
        'parser.ExamQuestion',
        on_delete=models.CASCADE,
        related_name='course_links',
        db_column='question_id',
        verbose_name='习题',
    )
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, verbose_name='来源')
    source_course_name = models.CharField(max_length=200, null=True, blank=True, verbose_name='源课程名称')
    is_deleted = models.BooleanField(default=False, verbose_name='软删除标记')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'course_question_link'
        verbose_name = '课程习题关联'
        verbose_name_plural = '课程习题关联'
        unique_together = ('course', 'question')

    def __str__(self):
        return f'{self.course} -> {self.question}'


class VariantTask(models.Model):
    """变式题生成任务"""
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('running', '处理中'),
        ('success', '处理成功'),
        ('failed', '处理失败'),
    ]

    id = models.BigAutoField(primary_key=True)
    original_question = models.ForeignKey(
        'parser.ExamQuestion',
        on_delete=models.CASCADE,
        related_name='variant_tasks',
        db_column='original_question_id',
        verbose_name='原始题目',
    )
    variant_mode = models.CharField(max_length=30, verbose_name='变式模式')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    generator_result = models.JSONField(null=True, blank=True, verbose_name='生成器结果')
    verifier_result = models.JSONField(null=True, blank=True, verbose_name='校验器结果')
    generated_question = models.JSONField(null=True, blank=True, verbose_name='生成的题目')
    error_message = models.TextField(null=True, blank=True, verbose_name='错误信息')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        db_table = 'course_variant_task'
        verbose_name = '变式题任务'
        verbose_name_plural = '变式题任务'

    def __str__(self):
        return f'VariantTask({self.variant_mode}, {self.status})'
