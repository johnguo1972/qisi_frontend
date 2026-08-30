"""KnowledgePoint model mapping to existing knowledge_points table."""

import uuid_utils.compat as uuid_compat
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


class KnowledgeTopic(models.Model):
    """A controlled, versioned topic node used by the AI probe workflow."""

    id = models.CharField(max_length=120, primary_key=True)
    subject = models.CharField(max_length=50, choices=KnowledgePoint.SUBJECT_CHOICES)
    stage = models.CharField(max_length=20, choices=KnowledgePoint.STAGE_CHOICES)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE,
        related_name='children',
    )
    name = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)
    catalog_version = models.CharField(max_length=64, default='v1')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'knowledge_controlled_topic'
        ordering = ('sort_order', 'id')
        indexes = [
            models.Index(
                fields=('subject', 'stage', 'parent', 'is_enabled'),
                name='knowledge_topic_scope_idx',
            ),
        ]

    @property
    def path_ids(self) -> list[str]:
        """Return the stable root-to-self identifier path without recursion."""
        path: list[str] = []
        node = self
        seen: set[str] = set()
        while node is not None:
            if node.id in seen:
                raise ValueError('knowledge topic hierarchy contains a cycle')
            seen.add(node.id)
            path.append(str(node.id))
            node = node.parent
        return list(reversed(path))


class KnowledgeTopicModule(models.Model):
    """A controlled topic to a standard knowledge-point module link."""

    topic = models.ForeignKey(
        KnowledgeTopic, on_delete=models.CASCADE, related_name='module_links',
    )
    module = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'knowledge_controlled_topic_module'
        ordering = ('sort_order', 'id')
        constraints = [
            models.UniqueConstraint(
                fields=('topic', 'module'),
                name='knowledge_topic_module_unique',
            ),
        ]
        indexes = [
            models.Index(
                fields=('module', 'is_enabled'),
                name='kn_topic_module_lookup_idx',
            ),
        ]


class QuestionKnowledgeMatch(models.Model):
    """Auditable relation between a question and a knowledge point."""

    SOURCE_CHOICES = [
        ('manual', 'manual'), ('import', 'import'),
        ('rule', 'rule'), ('ai', 'ai'),
    ]
    STATUS_CHOICES = [
        ('suggested', 'suggested'), ('confirmed', 'confirmed'),
        ('rejected', 'rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid_compat.uuid7, editable=False)
    question = models.ForeignKey(
        'parser.ExamQuestion', on_delete=models.CASCADE,
        related_name='knowledge_matches', db_column='question_id',
    )
    knowledge_point = models.ForeignKey(
        KnowledgePoint, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='question_matches', db_column='knowledge_point_id',
        db_constraint=False,
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='rule')
    source_version = models.CharField(max_length=30, default='rule-v1')
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='suggested')
    evidence = models.JSONField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        'accounts.UserAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confirmed_question_knowledge_matches',
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'question_knowledge_match'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['question', 'knowledge_point', 'source_version'],
                name='uq_question_kp_match_version',
            ),
        ]
