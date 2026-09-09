from django.core.management.base import BaseCommand
from django.db import transaction

from apps.common.codegen import reconcile_question_id_counter


class Command(BaseCommand):
    help = 'Report or reconcile the next question system-ID sequence for one subject.'

    def add_arguments(self, parser):
        parser.add_argument('--subject', required=True, help='Question system-ID subject prefix, such as P.')
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Persist the safe next sequence. Without this flag, only report it.',
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            result = reconcile_question_id_counter(
                options['subject'],
                apply=options['apply'],
            )

        state = 'updated' if options['apply'] and result['changed'] else 'unchanged'
        self.stdout.write(
            f"subject={result['subject']} prefix={result['letter']} "
            f"previous_next={result['previous_next_seq']} "
            f"highest_existing={result['highest_existing']} "
            f"safe_next={result['next_seq']} {state}"
        )
