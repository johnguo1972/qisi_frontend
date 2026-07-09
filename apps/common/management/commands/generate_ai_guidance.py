from django.core.management.base import BaseCommand
from apps.parser.models import ExamQuestion
from apps.common.ai_service import AIReviewService


class Command(BaseCommand):
    help = 'Generate AI guidance data (answer_b) for questions'

    def add_arguments(self, parser):
        parser.add_argument('question_ids', nargs='+', type=int, help='Question IDs to process')
        parser.add_argument('--all', action='store_true', help='Process all questions with missing ai_answer_b')

    def handle(self, *args, **options):
        service = AIReviewService()
        
        if options['all']:
            questions = ExamQuestion.objects.filter(ai_answer_b__isnull=True)
            self.stdout.write(f'Found {questions.count()} questions with missing ai_answer_b')
        else:
            questions = ExamQuestion.objects.filter(id__in=options['question_ids'])
        
        for question in questions:
            self.stdout.write(f'Processing question {question.id}...')
            try:
                results = service.process_question_full(question.id)
                if 'answer_b' in results and not results['answer_b'].get('error'):
                    question.ai_answer_b = results['answer_b']
                    question.save()
                    self.stdout.write(self.style.SUCCESS(f'✓ Question {question.id} updated'))
                else:
                    self.stdout.write(self.style.WARNING(f'⚠ Question {question.id} generation failed'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Question {question.id} error: {e}'))