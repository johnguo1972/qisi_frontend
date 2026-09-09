from io import StringIO

import pytest
from django.core.management import call_command

from apps.papers.models import ExamPaper, QuestionIDCounter
from apps.parser.models import ExamQuestion


@pytest.mark.django_db
def test_reconcile_question_id_counter_reports_then_applies_the_safe_sequence():
    paper = ExamPaper.objects.create(title='Counter reconciliation', subject='physics')
    ExamQuestion.objects.create(
        paper=paper,
        question_no='highest',
        question_type='single_choice',
        system_id='P00010',
        stem='Existing question',
    )
    QuestionIDCounter.objects.create(subject='P', next_seq=1)

    dry_run = StringIO()
    call_command('reconcile_question_id_counter', '--subject', 'P', stdout=dry_run)

    assert 'safe_next=17' in dry_run.getvalue()
    assert QuestionIDCounter.objects.get(subject='P').next_seq == 1

    applied = StringIO()
    call_command('reconcile_question_id_counter', '--subject', 'P', '--apply', stdout=applied)

    assert 'updated' in applied.getvalue()
    assert QuestionIDCounter.objects.get(subject='P').next_seq == 17
