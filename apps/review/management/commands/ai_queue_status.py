import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.review.models import AIProcessingJob, AIProcessingJobItem


class Command(BaseCommand):
    help = 'Report durable AI queue counters without sensitive payloads.'

    def handle(self, *args, **options):
        counts = {row['status']: row['count'] for row in AIProcessingJobItem.objects.values('status').annotate(count=Count('id'))}
        payload = {
            'capacity': int(getattr(settings, 'AI_QUEUE_CAPACITY', 10000)),
            'active_jobs': AIProcessingJob.objects.filter(status__in=('queued', 'running')).count(),
            'queued': counts.get('queued', 0), 'dispatched': counts.get('dispatched', 0),
            'running': counts.get('running', 0), 'succeeded': counts.get('succeeded', 0),
            'partial': counts.get('partial', 0), 'failed': counts.get('failed', 0),
            'cancelled': counts.get('cancelled', 0),
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
