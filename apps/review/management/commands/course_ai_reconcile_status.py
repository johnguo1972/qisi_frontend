import json

from django.core.management.base import BaseCommand, CommandError

from apps.review.tasks import get_course_reconcile_status


class Command(BaseCommand):
    help = 'Show a course AI reconciliation report from the Redis result cache.'

    def add_arguments(self, parser):
        parser.add_argument('--batch-id', required=True)

    def handle(self, *args, **options):
        batch_id = str(options['batch_id'])
        payload = get_course_reconcile_status(batch_id)
        if payload is None:
            raise CommandError(f'Unknown or expired batch: {batch_id}')
        self.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
