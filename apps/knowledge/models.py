"""KnowledgePoint model mapping to existing knowledge_points table."""
from django.db import models


class KnowledgePoint(models.Model):
    SUBJECT_CHOICES = [('math', '数学'), ('physics', '物理')]
    STAGE_CHOICES = [('primary', '小学'), ('junior', '初中'), ('senior', '高中')]
    TERM_CHOICES = [('up', '上学期'), ('down', '下学期')]
    NODE_TYPE_CHOICES = [
        ('formula', '公式'), ('property', '属性'), ('method', '方法'),
        ('type', '类型'), ('general', '通用'),
    ]
    STAGE_LABELS = {
        'primary': '小学', 'junior': '初中', 'senior': '高中',
    }
    TERM_LABELS = {
        'up': '上学期', 'down': '下学期',
    }
    GRADE_LABELS = {
        1: '一年级', 2: '二年级', 3: '三年级', 4: '四年级',
        5: '五年级', 6: '六年级', 7: '七年级', 8: '八年级',
        9: '九年级', 10: '高一', 11: '高二', 12: '高三',
    }

    class Meta:
        db_table = 'knowledge_points'
        managed = False
        verbose_name = '知识点'
        verbose_name_plural = '知识点'

    id = models.BigAutoField(primary_key=True)
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    grade_index = models.PositiveSmallIntegerField()
    grade_name = models.CharField(max_length=20)
    term = models.CharField(max_length=10, choices=TERM_CHOICES)
    chapter = models.CharField(max_length=255)
    module = models.CharField(max_length=255)
    node_type = models.CharField(max_length=20, choices=NODE_TYPE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_subject_display()}-{self.chapter}-{self.module}'

    @property
    def full_label(self):
        """Return human-readable label like '数学-小学-一年级上学期'."""
        stage = self.STAGE_LABELS.get(self.stage, self.stage)
        grade = self.GRADE_LABELS.get(self.grade_index, self.grade_name)
        term = self.TERM_LABELS.get(self.term, self.term)
        return f'{self.get_subject_display()}-{stage}-{grade}{term}'
