"""Parser models for exam page parsing results."""
from django.db import models
from apps.papers.models import ExamPaper
from apps.common import status as const


_PAGE_STATUS_LABELS = {
    const.PAGE_PENDING: '等待中',
    const.PAGE_CONVERTED: '已转换',
    const.PAGE_PARSING: '解析中',
    const.PAGE_PARSED: '已解析',
    const.PAGE_PARSE_FAILED: '解析失败',
    const.PAGE_NEED_REVIEW: '待审核',
}


class ExamPage(models.Model):
    """Represents a single page image of an exam paper."""
    paper = models.ForeignKey(
        ExamPaper, on_delete=models.CASCADE, related_name='pages',
        db_column='paper_id'
    )
    page_no = models.IntegerField(verbose_name='页码')
    image_path = models.CharField(max_length=500, verbose_name='图片路径')
    width = models.IntegerField(null=True, blank=True, verbose_name='宽度')
    height = models.IntegerField(null=True, blank=True, verbose_name='高度')
    ocr_text = models.TextField(null=True, blank=True, verbose_name='OCR文本')
    layout_json = models.JSONField(null=True, blank=True, verbose_name='布局JSON')
    parse_status = models.CharField(max_length=50, default='pending', verbose_name='解析状态')
    ai_confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True, verbose_name='AI置信度')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tiku_exam_page'
        verbose_name = '试卷页面'
        verbose_name_plural = '试卷页面'
        unique_together = ('paper', 'page_no')

    def __str__(self):
        return f'{self.paper.title} - Page {self.page_no}'

    def get_parse_status_display_label(self):
        """Return human-readable page status label."""
        return _PAGE_STATUS_LABELS.get(self.parse_status, self.parse_status)


class AIParseResult(models.Model):
    """Stores raw AI parsing results."""
    paper = models.ForeignKey(
        ExamPaper, on_delete=models.CASCADE, related_name='ai_results',
        db_column='paper_id'
    )
    page = models.ForeignKey(
        ExamPage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ai_results', db_column='page_id'
    )
    model_name = models.CharField(max_length=100, default='qwen3-vl-plus', verbose_name='模型名称')
    prompt_version = models.CharField(max_length=50, null=True, blank=True, verbose_name='Prompt版本')
    request_json = models.JSONField(null=True, blank=True, verbose_name='请求JSON')
    response_json = models.JSONField(null=True, blank=True, verbose_name='响应JSON')
    raw_response = models.TextField(null=True, blank=True, verbose_name='原始响应')
    is_valid_json = models.BooleanField(default=False, verbose_name='是否有效JSON')
    error_message = models.TextField(null=True, blank=True, verbose_name='错误信息')
    latency_ms = models.IntegerField(null=True, blank=True, verbose_name='延迟(毫秒)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tiku_ai_parse_result'
        verbose_name = 'AI解析结果'
        verbose_name_plural = 'AI解析结果'

    def __str__(self):
        return f'AI Result for {self.paper} (page {self.page.page_no if self.page else "N/A"})'


class ExamQuestion(models.Model):
    """Represents a parsed exam question."""
    paper = models.ForeignKey(
        ExamPaper, on_delete=models.CASCADE, related_name='questions',
        db_column='paper_id'
    )
    question_no = models.CharField(max_length=50, verbose_name='题号')
    system_id = models.CharField(
        max_length=10, unique=True, null=True, blank=True,
        verbose_name='系统编号', db_index=True,
        help_text='如：M00001',
    )
    paper_question_no = models.CharField(
        max_length=50, null=True, blank=True,
        verbose_name='试卷题号', db_index=True,
        help_text='如：M90001-1-3',
    )
    parent_question = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sub_questions', db_column='parent_question_id',
        verbose_name='父题'
    )
    section_title = models.CharField(max_length=255, null=True, blank=True, verbose_name='大题标题')
    question_type = models.CharField(max_length=50, verbose_name='题型')
    subject = models.CharField(max_length=50, null=True, blank=True, verbose_name='学科')

    stem = models.TextField(verbose_name='题干')
    stem_html = models.TextField(null=True, blank=True, verbose_name='题干HTML')
    answer = models.TextField(null=True, blank=True, verbose_name='答案')
    analysis = models.TextField(null=True, blank=True, verbose_name='解析')
    solution = models.TextField(null=True, blank=True, verbose_name='详解')
    comment = models.TextField(null=True, blank=True, verbose_name='点评')
    raw_explanation = models.TextField(null=True, blank=True, verbose_name='原始解释')
    raw_text = models.TextField(null=True, blank=True, verbose_name='原始文本')

    knowledge_points = models.JSONField(null=True, blank=True, verbose_name='知识点')
    difficulty = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, verbose_name='难度')
    original_question = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='modified_versions', db_column='original_question_id',
        verbose_name='原始题目'
    )

    page_start = models.IntegerField(null=True, blank=True, verbose_name='起始页')
    page_end = models.IntegerField(null=True, blank=True, verbose_name='结束页')
    bbox = models.JSONField(null=True, blank=True, verbose_name='主区域bbox')
    region_json = models.JSONField(null=True, blank=True, verbose_name='跨页区域')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True, verbose_name='置信度')
    formula_need_review = models.BooleanField(default=False, verbose_name='公式需复核')
    need_review = models.BooleanField(default=True, verbose_name='需人工校验')
    review_status = models.CharField(max_length=50, default='unreviewed', verbose_name='复核状态')
    parse_status = models.CharField(max_length=50, default='auto_parsed', verbose_name='解析状态')

    # AI review fields
    ai_answer_a = models.JSONField(null=True, blank=True, verbose_name='AI答案A模式')
    ai_answer_b = models.JSONField(null=True, blank=True, verbose_name='AI答案B模式')
    ai_answer_c = models.JSONField(null=True, blank=True, verbose_name='AI答案C模式')
    ai_knowledge_enrichment = models.JSONField(null=True, blank=True, verbose_name='AI知识点 enrich')

    # AI processing pipeline fields
    ai_probe_result = models.JSONField(null=True, blank=True, verbose_name='AI探查结果')
    ai_vision_extract = models.JSONField(null=True, blank=True, verbose_name='AI读图结果')
    ai_verifier_result = models.JSONField(null=True, blank=True, verbose_name='AI校验结果')
    ai_processed_at = models.DateTimeField(null=True, blank=True, verbose_name='AI处理时间')
    ai_processing_status = models.CharField(
        max_length=20, default='pending',
        choices=[
            ('pending', '待处理'),
            ('running', '处理中'),
            ('success', '处理成功'),
            ('failed', '处理失败'),
        ],
        verbose_name='AI处理状态',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tiku_exam_question'
        verbose_name = '题目'
        verbose_name_plural = '题目'
        indexes = [
            models.Index(fields=['paper', 'question_no'], name='idx_paper_question'),
            models.Index(fields=['question_type'], name='idx_question_type'),
            models.Index(fields=['review_status'], name='idx_review_status'),
            models.Index(fields=['system_id'], name='idx_system_id'),
            models.Index(fields=['paper_question_no'], name='idx_paper_qno'),
        ]

    def __str__(self):
        no = self.paper_question_no or f'Q{self.question_no}'
        return f'{no}: {self.stem[:50]}'

    QUESTION_TYPE_LABELS = {
        const.QT_SINGLE_CHOICE: '单选题',
        const.QT_MULTIPLE_CHOICE: '多选题',
        const.QT_FILL_BLANK: '填空题',
        const.QT_SHORT_ANSWER: '简答题',
        const.QT_ESSAY: '作文题',
        const.QT_TRUE_FALSE: '判断题',
        const.QT_COMPUTATION: '计算题',
        const.QT_PROOF: '证明题',
        const.QT_UNKNOWN: '未知',
    }

    REVIEW_STATUS_LABELS = {
        'unreviewed': '未审核',
        'reviewed': '已审核',
        'confirmed': '已确认',
        'rejected': '已驳回',
        'need_review': '待审核',
    }

    def get_question_type_display_label(self):
        """Return human-readable question type label."""
        return self.QUESTION_TYPE_LABELS.get(self.question_type, self.question_type)

    def get_review_status_display_label(self):
        """Return human-readable review status label."""
        return self.REVIEW_STATUS_LABELS.get(self.review_status, self.review_status)


class QuestionOption(models.Model):
    """Represents an option (A/B/C/D) of a multiple choice question."""
    question = models.ForeignKey(
        ExamQuestion, on_delete=models.CASCADE, related_name='options',
        db_column='question_id'
    )
    option_label = models.CharField(max_length=10, verbose_name='选项标签')
    content = models.TextField(verbose_name='选项内容')
    content_html = models.TextField(null=True, blank=True, verbose_name='选项HTML')
    bbox = models.JSONField(null=True, blank=True, verbose_name='bbox')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tiku_question_option'
        verbose_name = '选项'
        verbose_name_plural = '选项'
        unique_together = ('question', 'option_label')

    def __str__(self):
        return f'{self.question.question_no} - {self.option_label}'


class QuestionImage(models.Model):
    """Represents an image associated with a question."""
    paper = models.ForeignKey(
        ExamPaper, on_delete=models.CASCADE, related_name='question_images',
        db_column='paper_id'
    )
    question = models.ForeignKey(
        ExamQuestion, on_delete=models.CASCADE, related_name='images',
        db_column='question_id'
    )
    page = models.ForeignKey(
        ExamPage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='question_images', db_column='page_id'
    )

    image_type = models.CharField(max_length=50, default='other', verbose_name='图片类型')
    file_path = models.CharField(max_length=500, verbose_name='文件路径')
    source_page_image_path = models.CharField(max_length=500, null=True, blank=True, verbose_name='源页面图路径')

    bbox = models.JSONField(null=True, blank=True, verbose_name='原始bbox')
    expanded_bbox = models.JSONField(null=True, blank=True, verbose_name='扩边bbox')
    description = models.CharField(max_length=500, null=True, blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tiku_question_image'
        verbose_name = '题目插图'
        verbose_name_plural = '题目插图'

    def __str__(self):
        return f'Image for Q{self.question.question_no} ({self.image_type})'
