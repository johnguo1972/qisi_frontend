from django.core.management.base import BaseCommand

from apps.knowledge.matching import RULE_VERSION, rebuild_question_matches
from apps.knowledge.models import QuestionKnowledgeMatch
from apps.parser.models import ExamQuestion


class Command(BaseCommand):
    help = '为历史上没有知识点 JSON 的题目生成规则匹配建议'

    def add_arguments(self, parser):
        parser.add_argument('--question-id', action='append', dest='question_ids')
        parser.add_argument('--limit', type=int, default=0)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        qs = ExamQuestion.objects.select_related('paper').order_by('created_at')
        if options['question_ids']:
            qs = qs.filter(id__in=options['question_ids'])
        if options['limit']:
            qs = qs[:max(options['limit'], 1)]
        question_count = match_count = skipped = 0
        for question in qs.iterator():
            if question.knowledge_points or QuestionKnowledgeMatch.objects.filter(
                question=question, source='rule', source_version=RULE_VERSION,
            ).exists():
                skipped += 1
                continue
            question_count += 1
            if not options['dry_run']:
                match_count += len(rebuild_question_matches(question))
        self.stdout.write(self.style.SUCCESS(
            f'processed={question_count}, created_matches={match_count}, skipped={skipped}, dry_run={options["dry_run"]}'
        ))
