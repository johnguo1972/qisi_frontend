from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import UserAccount
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion
from apps.study.models import QuestionRelation
from apps.study.question_relation_service import (
    canonical_question_pair,
    find_relation_candidates,
    knowledge_point_keys,
)


@pytest.fixture
def teacher(db):
    return UserAccount.objects.create(
        role_type='teacher',
        mobile='13900008881',
        display_name='Relation Teacher',
        subject='physics',
        subjects=['physics'],
    )


@pytest.fixture
def paper(db):
    return ExamPaper.objects.create(
        title='Relation Questions',
        subject='physics',
        source_file_path='tests/relations.pdf',
    )


@pytest.fixture
def questions(paper):
    def create(question_no, *, subject='physics', difficulty=Decimal('3.00'), points=None):
        return ExamQuestion.objects.create(
            paper=paper,
            question_no=question_no,
            question_type='single_choice',
            subject=subject,
            stem=f'Question {question_no}',
            difficulty=difficulty,
            knowledge_points=points or [],
        )

    return {
        'origin': create(
            'origin',
            points=[
                {'id': 'kp-speed'},
                {'module': 'motion'},
            ],
        ),
        'id_match': create('id-match', difficulty=Decimal('2.50'), points=[{'id': 'kp-speed'}]),
        'module_match': create('module-match', difficulty=Decimal('3.50'), points=[{'module': 'motion'}]),
        'too_easy': create('too-easy', difficulty=Decimal('2.49'), points=[{'id': 'kp-speed'}]),
        'too_hard': create('too-hard', difficulty=Decimal('3.51'), points=[{'module': 'motion'}]),
        'other_subject': create('other-subject', subject='math', points=[{'id': 'kp-speed'}]),
        'unrelated': create('unrelated', points=[{'id': 'kp-force'}]),
        'name_origin': create('name-origin', points=[{'name': 'Uniform motion'}]),
        'name_match': create('name-match', points=['Uniform motion']),
    }


@pytest.mark.django_db
def test_canonical_pair_is_unique_and_readable_from_both_directions(teacher, questions):
    relation = QuestionRelation.create_for_questions(
        questions['id_match'], questions['origin'], teacher
    )

    assert str(relation.question_left_id) < str(relation.question_right_id)
    assert QuestionRelation.for_question(questions['origin']).get() == relation
    assert QuestionRelation.for_question(questions['id_match']).get() == relation


@pytest.mark.django_db
def test_candidate_service_accepts_shared_id_or_module_and_inclusive_half_point_boundary(questions):
    candidates, reason = find_relation_candidates(
        questions['origin'], ExamQuestion.objects.all()
    )

    assert reason is None
    assert {item.id for item in candidates} == {
        questions['id_match'].id,
        questions['module_match'].id,
    }


@pytest.mark.django_db
def test_candidate_service_matches_legacy_string_to_knowledge_point_name(questions):
    candidates, reason = find_relation_candidates(
        questions['name_origin'], ExamQuestion.objects.all()
    )

    assert reason is None
    assert [item.id for item in candidates] == [questions['name_match'].id]


@pytest.mark.django_db
def test_candidate_service_excludes_an_already_related_question(teacher, questions):
    QuestionRelation.create_for_questions(questions['origin'], questions['id_match'], teacher)

    candidates, reason = find_relation_candidates(
        questions['origin'], ExamQuestion.objects.all()
    )

    assert reason is None
    assert questions['id_match'].id not in {item.id for item in candidates}


def test_knowledge_point_keys_normalizes_id_module_name_and_legacy_strings():
    assert knowledge_point_keys(
        {
            'points': [
                {'id': 42, 'module': 'ignored-by-id-priority'},
                {'module': 'Motion'},
                {'name': 'Speed'},
                'Legacy point',
            ]
        }
    ) == {
        'id:42',
        'module:Motion',
        'name:Speed',
        'name:Legacy point',
    }


@pytest.mark.django_db
def test_candidate_service_returns_a_fixed_reason_when_origin_metadata_is_missing(questions):
    questions['origin'].subject = ''
    questions['origin'].save(update_fields=['subject'])

    candidates, reason = find_relation_candidates(
        questions['origin'], ExamQuestion.objects.all()
    )

    assert candidates == []
    assert reason == '当前题目缺少学科、难度或知识点，无法生成可关联题'


@pytest.mark.django_db
def test_relation_cannot_point_to_itself_or_duplicate_pair(teacher, questions):
    with pytest.raises(ValidationError):
        QuestionRelation.create_for_questions(questions['origin'], questions['origin'], teacher)

    QuestionRelation.create_for_questions(questions['origin'], questions['id_match'], teacher)

    with pytest.raises(IntegrityError):
        QuestionRelation.create_for_questions(questions['id_match'], questions['origin'], teacher)


@pytest.mark.django_db
def test_relation_database_rejects_self_and_reverse_pairs_bypassing_the_factory(teacher, questions):
    left, right = canonical_question_pair(questions['origin'], questions['id_match'])

    with transaction.atomic():
        with pytest.raises(IntegrityError):
            QuestionRelation.objects.create(
                question_left=right,
                question_right=left,
                created_by=teacher,
            )

    with transaction.atomic():
        with pytest.raises(IntegrityError):
            QuestionRelation.objects.create(
                question_left=left,
                question_right=left,
                created_by=teacher,
            )
