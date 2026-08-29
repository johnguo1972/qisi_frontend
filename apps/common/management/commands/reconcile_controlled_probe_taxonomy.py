"""Queue controlled probe repairs without creating A/B/C answer work."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.parser.models import ExamQuestion
from apps.review.tasks import (
    is_ai_knowledge_complete,
    is_ai_probe_complete,
    single_probe_ai_process_question,
)
from apps.study.models import QuestionTagRelation


class Command(BaseCommand):
    help = (
        'Queue only the controlled AI probe for tagged questions that do not '
        'yet have a complete controlled taxonomy and module selection.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tag', required=True, help='题目 JSON 标签或标签关系名称')
        parser.add_argument('--limit', type=int, default=None, help='最多排队题数')
        parser.add_argument('--model', default=None, help='兼容参数；默认使用配置路由')
        parser.add_argument('--dry-run', action='store_true', help='仅输出计划，不创建 Celery 任务')

    def handle(self, *args, **options):
        tag = str(options['tag']).strip()
        if not tag:
            raise CommandError('--tag 不能为空')
        limit = options.get('limit')
        if limit is not None and limit < 1:
            raise CommandError('--limit 必须大于 0')

        relation_ids = QuestionTagRelation.objects.filter(
            tag__name=tag,
        ).values('question_id')
        queryset = ExamQuestion.objects.filter(
            Q(tags__contains=[tag]) | Q(id__in=relation_ids)
        ).order_by('created_at', 'id').distinct()

        total = 0
        skipped = 0
        pending_ids: list[str] = []
        for question in queryset.iterator():
            total += 1
            if is_ai_probe_complete(question) and is_ai_knowledge_complete(question):
                skipped += 1
                continue
            if limit is not None and len(pending_ids) >= limit:
                continue
            pending_ids.append(str(question.id))

        queued = 0
        if not options['dry_run']:
            for question_id in pending_ids:
                single_probe_ai_process_question.delay(
                    question_id,
                    model=options.get('model'),
                )
                queued += 1

        summary = {
            'tag': tag,
            'total': total,
            'already_complete': skipped,
            'selected': len(pending_ids),
            'queued': queued,
            'dry_run': bool(options['dry_run']),
        }
        self.stdout.write(self.style.SUCCESS(str(summary)))
