import json
import uuid

from django.core.management.base import BaseCommand

from apps.review.tasks import start_course_ai_reconcile


class Command(BaseCommand):
    help = 'Queue a two-round missing-only AI reconciliation for one course.'

    def add_arguments(self, parser):
        parser.add_argument('--course-id', required=True)

    def handle(self, *args, **options):
        course_id = str(options['course_id'])
        batch_id = str(uuid.uuid4())
        task = start_course_ai_reconcile.apply_async(
            args=(course_id, batch_id),
            queue='ai.batch',
        )
        self.stdout.write(json.dumps({
            'batch_id': batch_id,
            'starter_task_id': str(task.id),
            'course_id': course_id,
            'status': 'queued',
        }, ensure_ascii=False))
