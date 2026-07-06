"""ExamPaper and ParseTask models."""
from django.db import models
from apps.common import status as const


# Display labels for status constants
_PAPER_STATUS_LABELS = {
    const.PAPER_UPLOADED: '已上传',
    const.PAPER_CONVERTING: '转换中',
    const.PAPER_CONVERTED: '已转换',
    const.PAPER_PARSING: '解析中',
    const.PAPER_POSTPROCESSING: '后处理中',
    const.PAPER_CROPPING: '裁剪中',
    const.PAPER_REVIEWING: '待审核',
    const.PAPER_FINISHED: '已完成',
    const.PAPER_FAILED: '失败',
}

_TASK_STATUS_LABELS = {
    const.TASK_PENDING: '等待中',
    const.TASK_RUNNING: '运行中',
    const.TASK_SUCCESS: '成功',
    const.TASK_FAILED: '失败',
    const.TASK_RETRYING: '重试中',
    const.TASK_CANCELLED: '已取消',
}

_PAGE_STATUS_LABELS = {
    const.PAGE_PENDING: '等待中',
    const.PAGE_CONVERTED: '已转换',
    const.PAGE_PARSING: '解析中',
    const.PAGE_PARSED: '已解析',
    const.PAGE_PARSE_FAILED: '解析失败',
    const.PAGE_NEED_REVIEW: '待审核',
}


class ExamPaper(models.Model):
    """Represents an uploaded exam paper."""
    title = models.CharField(max_length=255, verbose_name='试卷名称')
    paper_code = models.CharField(
        max_length=20, unique=True, null=True, blank=True,
        verbose_name='试卷编号', db_index=True,
        help_text='如：M90001, PA0002',
    )
    region = models.CharField(
        max_length=100, null=True, blank=True,
        verbose_name='来源地区',
        help_text='如：全国卷, 广东卷, 深圳卷',
    )
    subject = models.CharField(max_length=50, verbose_name='学科')
    stage = models.CharField(max_length=50, null=True, blank=True, verbose_name='学段')
    grade = models.CharField(max_length=50, null=True, blank=True, verbose_name='年级')
    paper_type = models.CharField(max_length=50, null=True, blank=True, verbose_name='试卷类型')
    has_solution = models.BooleanField(default=False, verbose_name='是否含答案解析')
    uploaded_by = models.ForeignKey(
        'accounts.UserAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='uploaded_papers', verbose_name='上传者',
        help_text='上传该试卷的老师',
    )
    source_file_path = models.CharField(max_length=500, verbose_name='源文件路径')
    pdf_file_path = models.CharField(max_length=500, null=True, blank=True, verbose_name='PDF路径')
    total_pages = models.IntegerField(default=0, verbose_name='总页数')
    total_questions = models.IntegerField(default=0, verbose_name='总题数')
    status = models.CharField(max_length=50, default='uploaded', verbose_name='状态')
    error_message = models.TextField(null=True, blank=True, verbose_name='错误信息')
    is_deleted = models.BooleanField(default=False, verbose_name='已删除', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tiku_exam_paper'
        verbose_name = '试卷'
        verbose_name_plural = '试卷'

    def __str__(self):
        return self.title

    def get_status_display_label(self):
        """Return human-readable status label."""
        return _PAPER_STATUS_LABELS.get(self.status, self.status)


class ParseTask(models.Model):
    """Represents an async parsing task."""
    paper = models.ForeignKey(
        ExamPaper, on_delete=models.CASCADE, related_name='tasks',
        db_column='paper_id'
    )
    question = models.ForeignKey(
        'parser.ExamQuestion', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reparse_tasks',
        db_column='question_id', verbose_name='试题'
    )
    task_type = models.CharField(max_length=50, verbose_name='任务类型')
    status = models.CharField(max_length=50, default='pending', verbose_name='状态')
    progress = models.IntegerField(default=0, verbose_name='进度')
    current_step = models.CharField(max_length=255, null=True, blank=True, verbose_name='当前步骤')
    error_message = models.TextField(null=True, blank=True, verbose_name='错误信息')
    retry_count = models.IntegerField(default=0, verbose_name='重试次数')
    celery_task_id = models.CharField(max_length=255, null=True, blank=True, verbose_name='Celery任务ID')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tiku_parse_task'
        verbose_name = '解析任务'
        verbose_name_plural = '解析任务'
        indexes = [models.Index(fields=['status'], name='idx_task_status')]

    def __str__(self):
        return f'Task {self.id} for {self.paper.title} ({self.status})'

    def get_status_display_label(self):
        """Return human-readable status label."""
        return _TASK_STATUS_LABELS.get(self.status, self.status)


class PaperCodeCounter(models.Model):
    """Tracks the next sequence number for paper code generation.
    Uses letter (e.g. 'M', 'P') rather than full subject name
    to avoid collisions between different subject names mapping to same letter."""
    letter = models.CharField(max_length=1)
    grade_char = models.CharField(max_length=1)
    next_seq = models.IntegerField(default=1)

    class Meta:
        db_table = 'tiku_paper_code_counter'
        unique_together = ('letter', 'grade_char')
        verbose_name = '试卷编号计数器'
        verbose_name_plural = '试卷编号计数器'

    def __str__(self):
        return f'{self.letter}+{self.grade_char} -> {self.next_seq:04d}'


class QuestionIDCounter(models.Model):
    """Tracks the next hex sequence number for question system IDs."""
    subject = models.CharField(max_length=50, unique=True)
    next_seq = models.IntegerField(default=1)

    class Meta:
        db_table = 'tiku_question_id_counter'
        verbose_name = '题目系统编号计数器'
        verbose_name_plural = '题目系统编号计数器'

    def __str__(self):
        return f'{self.subject} -> {self.next_seq:05X}'
