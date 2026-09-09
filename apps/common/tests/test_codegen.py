import pytest
from django.db import transaction

from apps.common.codegen import generate_question_system_id
from apps.papers.models import ExamPaper, QuestionIDCounter
from apps.parser.models import ExamQuestion


@pytest.fixture
def physics_paper(db):
    return ExamPaper.objects.create(title='Question ID allocation', subject='physics')


@pytest.mark.django_db
def test_question_system_id_reconciles_a_stale_counter_to_the_highest_used_prefix(physics_paper):
    """A stale counter must not emit low IDs merely because their slots are empty."""
    ExamQuestion.objects.create(
        paper=physics_paper,
        question_no='existing-high-id',
        question_type='single_choice',
        system_id='P003E8',
        stem='Existing physical-science question',
    )
    QuestionIDCounter.objects.create(subject='P', next_seq=1)

    generated = generate_question_system_id('P')

    assert generated == 'P003E9'
    assert QuestionIDCounter.objects.get(subject='P').next_seq == 1002


@pytest.mark.django_db(transaction=True)
def test_question_system_id_reservation_rolls_back_with_the_outer_transaction(physics_paper):
    QuestionIDCounter.objects.create(subject='P', next_seq=7)

    with transaction.atomic():
        assert generate_question_system_id('P') == 'P00007'
        transaction.set_rollback(True)

    assert generate_question_system_id('P') == 'P00007'


@pytest.mark.django_db(transaction=True)
def test_question_system_id_reserves_distinct_values_for_successive_callers(physics_paper):
    first = generate_question_system_id('P')
    second = generate_question_system_id('P')

    assert (first, second) == ('P00001', 'P00002')
    assert QuestionIDCounter.objects.get(subject='P').next_seq == 3
