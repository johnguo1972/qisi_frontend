from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, QuestionOption
from apps.study.models import QuestionRelation
from apps.study import question_views
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
        stage='junior',
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


@pytest.fixture
def teacher_client(teacher):
    teacher.stages = ['junior']
    teacher.save(update_fields=['stages'])
    client = APIClient()
    client.force_authenticate(user=teacher)
    return client


@pytest.fixture
def relation_knowledge_point_table(db):
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_points (
                id BIGINT PRIMARY KEY,
                subject VARCHAR(50),
                stage VARCHAR(20),
                grade_index SMALLINT,
                grade_name VARCHAR(20),
                term VARCHAR(10),
                chapter VARCHAR(255),
                module VARCHAR(255),
                node_type VARCHAR(20),
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("DELETE FROM knowledge_points")
    yield
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM knowledge_points")


@pytest.fixture
def relation_questions(paper, relation_knowledge_point_table):
    def create(question_no, *, subject='physics', difficulty=Decimal('3.00'), points=None):
        return ExamQuestion.objects.create(
            paper=paper,
            question_no=question_no,
            question_type='single_choice',
            subject=subject,
            stem=f'Relation question {question_no}',
            difficulty=difficulty,
            knowledge_points=points or [],
        )

    origin = create('origin', points=[{'module': 'motion'}])
    match = create('match', points=[{'module': 'motion'}])
    second_match = create('second-match', points=[{'module': 'motion'}])
    return SimpleNamespace(
        origin=origin,
        match=match,
        second_match=second_match,
        other_subject=create('other-subject', subject='math', points=[{'module': 'motion'}]),
        too_hard=create('too-hard', difficulty=Decimal('3.51'), points=[{'module': 'motion'}]),
        unrelated=create('unrelated', points=[{'module': 'force'}]),
        missing_metadata=create('missing-metadata'),
    )


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


@pytest.mark.django_db
def test_relation_candidates_enforce_scope_subject_difficulty_knowledge_and_pagination(
    teacher_client, relation_questions
):
    response = teacher_client.get(
        f'/api/v1/questions/{relation_questions.origin.id}/relation-candidates/',
        {'page': 1, 'page_size': 50},
    )

    assert response.status_code == 200
    assert response.data['data']['total'] == 2
    assert response.data['data']['page_no'] == 1
    assert response.data['data']['page_size'] == 50
    assert response.data['data']['items'][0]['common_knowledge_point_names'] == ['motion']
    candidate_ids = {item['id'] for item in response.data['data']['items']}
    assert candidate_ids == {str(relation_questions.match.id), str(relation_questions.second_match.id)}


@pytest.mark.django_db
def test_relation_candidates_return_module_name_difficulty_and_option_previews(
    teacher_client, relation_questions, relation_knowledge_point_table,
):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO knowledge_points (id, subject, module) VALUES (%s, %s, %s)",
            [7, 'physics', 'motion'],
        )

    for question in (relation_questions.origin, relation_questions.match):
        question.knowledge_points = [{'id': 7}]
        question.save(update_fields=['knowledge_points'])
    QuestionOption.objects.create(
        question=relation_questions.match,
        option_label='A',
        content='$x^2$',
        sort_order=1,
    )

    response = teacher_client.get(
        f'/api/v1/questions/{relation_questions.origin.id}/relation-candidates/',
        {'page': 1, 'page_size': 10},
    )

    item = next(item for item in response.data['data']['items'] if item['id'] == str(relation_questions.match.id))
    assert item['common_knowledge_point_names'] == ['motion']
    assert item['difficulty'] == 3.0
    assert item['option_previews'] == [{'label': 'A', 'content': '$x^2$'}]


@pytest.mark.django_db
def test_create_list_and_remove_relation_is_direction_independent_and_idempotent(
    teacher_client, relation_questions
):
    relation_url = f'/api/v1/questions/{relation_questions.origin.id}/relations/'
    created = teacher_client.post(
        relation_url,
        {'question_ids': [str(relation_questions.match.id)]},
        format='json',
    )
    repeated_create = teacher_client.post(
        relation_url,
        {'question_ids': [str(relation_questions.match.id)]},
        format='json',
    )

    assert created.status_code == 200
    assert created.data['data'] == {
        'created_count': 1,
        'existing_count': 0,
        'invalid_question_ids': [],
    }
    assert repeated_create.data['data']['created_count'] == 0
    assert repeated_create.data['data']['existing_count'] == 1

    candidates_while_related = teacher_client.get(
        f'/api/v1/questions/{relation_questions.origin.id}/relation-candidates/'
    )
    assert {item['id'] for item in candidates_while_related.data['data']['items']} == {
        str(relation_questions.second_match.id),
    }

    listed = teacher_client.get(f'/api/v1/questions/{relation_questions.match.id}/relations/')
    assert listed.status_code == 200
    assert [item['id'] for item in listed.data['data']['items']] == [str(relation_questions.origin.id)]

    removed = teacher_client.delete(
        f'/api/v1/questions/{relation_questions.origin.id}/relations/{relation_questions.match.id}/'
    )
    repeated_remove = teacher_client.delete(
        f'/api/v1/questions/{relation_questions.match.id}/relations/{relation_questions.origin.id}/'
    )
    assert removed.data['data']['removed'] is True
    assert repeated_remove.data['data']['removed'] is False
    assert ExamQuestion.objects.filter(pk=relation_questions.match.pk).exists()

    candidates_after_removal = teacher_client.get(
        f'/api/v1/questions/{relation_questions.origin.id}/relation-candidates/'
    )
    assert {item['id'] for item in candidates_after_removal.data['data']['items']} == {
        str(relation_questions.match.id),
        str(relation_questions.second_match.id),
    }


@pytest.mark.django_db
def test_relation_mutations_reject_non_manager_and_invalid_or_out_of_scope_questions(
    teacher_client, teacher, relation_questions
):
    student = UserAccount.objects.create(
        role_type='student',
        mobile='13900008882',
        display_name='Relation Student',
    )
    student_client = APIClient()
    student_client.force_authenticate(user=student)
    relation_url = f'/api/v1/questions/{relation_questions.origin.id}/relations/'

    forbidden = student_client.post(
        relation_url,
        {'question_ids': [str(relation_questions.match.id)]},
        format='json',
    )
    invalid = teacher_client.post(
        relation_url,
        {
            'question_ids': [
                str(relation_questions.origin.id),
                str(relation_questions.other_subject.id),
                'not-a-uuid',
            ]
        },
        format='json',
    )

    assert forbidden.status_code == 403
    assert invalid.status_code == 200
    assert invalid.data['data'] == {
        'created_count': 0,
        'existing_count': 0,
        'invalid_question_ids': [
            str(relation_questions.origin.id),
            str(relation_questions.other_subject.id),
            'not-a-uuid',
        ],
    }


@pytest.mark.django_db
def test_relation_reads_do_not_leak_questions_outside_teacher_scope(teacher_client, teacher, relation_questions):
    QuestionRelation.create_for_questions(
        relation_questions.origin, relation_questions.other_subject, teacher
    )

    response = teacher_client.get(f'/api/v1/questions/{relation_questions.origin.id}/relations/')
    outside_origin = teacher_client.get(
        f'/api/v1/questions/{relation_questions.other_subject.id}/relation-candidates/'
    )

    assert response.status_code == 200
    assert response.data['data']['items'] == []
    assert outside_origin.status_code == 403


@pytest.mark.django_db
def test_relation_creation_enforces_candidates_but_keeps_existing_relation_idempotent(
    teacher_client, teacher, relation_questions
):
    teacher.subjects = ['physics', 'math']
    teacher.save(update_fields=['subjects'])
    relation_url = f'/api/v1/questions/{relation_questions.origin.id}/relations/'

    created = teacher_client.post(
        relation_url,
        {
            'question_ids': [
                str(relation_questions.match.id),
                str(relation_questions.other_subject.id),
                str(relation_questions.too_hard.id),
                str(relation_questions.unrelated.id),
                str(relation_questions.missing_metadata.id),
                str(relation_questions.origin.id),
            ]
        },
        format='json',
    )
    repeated = teacher_client.post(
        relation_url,
        {'question_ids': [str(relation_questions.match.id)]},
        format='json',
    )

    assert created.status_code == 200
    assert created.data['data'] == {
        'created_count': 1,
        'existing_count': 0,
        'invalid_question_ids': [
            str(relation_questions.other_subject.id),
            str(relation_questions.too_hard.id),
            str(relation_questions.unrelated.id),
            str(relation_questions.missing_metadata.id),
            str(relation_questions.origin.id),
        ],
    }
    assert repeated.data['data'] == {
        'created_count': 0,
        'existing_count': 1,
        'invalid_question_ids': [],
    }
    assert QuestionRelation.for_question(relation_questions.origin).count() == 1


@pytest.mark.django_db
def test_relation_creation_deduplicates_requests_and_rejects_more_than_100_ids(
    teacher_client, relation_questions
):
    relation_url = f'/api/v1/questions/{relation_questions.origin.id}/relations/'
    deduplicated = teacher_client.post(
        relation_url,
        {'question_ids': [str(relation_questions.match.id)] * 2},
        format='json',
    )
    oversized = teacher_client.post(
        relation_url,
        {'question_ids': [str(uuid4()) for _ in range(101)]},
        format='json',
    )

    assert deduplicated.status_code == 200
    assert deduplicated.data['data'] == {
        'created_count': 1,
        'existing_count': 0,
        'invalid_question_ids': [],
    }
    assert oversized.status_code == 400
    assert '100' in oversized.data['message']


@pytest.mark.django_db
def test_relation_gets_serialize_only_the_requested_page_and_default_to_50(
    monkeypatch, teacher_client, teacher, relation_questions
):
    extra_candidates = [
        ExamQuestion.objects.create(
            paper=relation_questions.origin.paper,
            question_no=f'extra-{number}',
            question_type='single_choice',
            subject='physics',
            stem=f'Extra relation question {number}',
            difficulty=Decimal('3.00'),
            knowledge_points=[{'module': 'motion'}],
        )
        for number in range(4)
    ]
    serialized_ids = []
    original_relation_item = question_views._relation_item

    default_candidates = teacher_client.get(
        f'/api/v1/questions/{relation_questions.origin.id}/relation-candidates/'
    )
    assert default_candidates.data['data']['page_size'] == 50

    def track_relation_item(question, common_names=None, knowledge_points_display=None):
        serialized_ids.append(str(question.id))
        return original_relation_item(question, common_names, knowledge_points_display)

    monkeypatch.setattr(question_views, '_relation_item', track_relation_item)
    candidates = teacher_client.get(
        f'/api/v1/questions/{relation_questions.origin.id}/relation-candidates/',
        {'page': 1, 'page_size': 2},
    )

    assert candidates.status_code == 200
    assert candidates.data['data']['page_size'] == 2
    assert serialized_ids == [item['id'] for item in candidates.data['data']['items']]
    assert len(serialized_ids) == 2

    serialized_ids.clear()
    all_related = [relation_questions.match, relation_questions.second_match, *extra_candidates]
    for related in all_related:
        QuestionRelation.create_for_questions(relation_questions.origin, related, teacher)
    listed = teacher_client.get(
        f'/api/v1/questions/{relation_questions.origin.id}/relations/',
        {'page': 1, 'page_size': 2},
    )

    assert listed.status_code == 200
    assert serialized_ids == [item['id'] for item in listed.data['data']['items']]
    assert len(serialized_ids) == 2

    serialized_ids.clear()
    default_page = teacher_client.get(
        f'/api/v1/questions/{relation_questions.origin.id}/relations/'
    )
    assert default_page.data['data']['page_size'] == 50


@pytest.mark.django_db
def test_relation_get_knowledge_point_queries_do_not_grow_with_page_size(
    teacher_client, teacher, relation_questions
):
    extra_questions = [
        ExamQuestion.objects.create(
            paper=relation_questions.origin.paper,
            question_no=f'query-count-{number}',
            question_type='single_choice',
            subject='physics',
            stem=f'Query count relation question {number}',
            difficulty=Decimal('3.00'),
            knowledge_points=[{'module': 'motion'}],
        )
        for number in range(4)
    ]
    candidates_url = f'/api/v1/questions/{relation_questions.origin.id}/relation-candidates/'
    relations_url = f'/api/v1/questions/{relation_questions.origin.id}/relations/'

    with CaptureQueriesContext(connection) as candidate_small_context:
        candidate_small = teacher_client.get(candidates_url, {'page': 1, 'page_size': 2})
    with CaptureQueriesContext(connection) as candidate_large_context:
        candidate_large = teacher_client.get(candidates_url, {'page': 1, 'page_size': 6})

    assert candidate_small.status_code == candidate_large.status_code == 200
    assert len(candidate_large_context) <= len(candidate_small_context) + 2

    for related in [relation_questions.match, relation_questions.second_match, *extra_questions]:
        QuestionRelation.create_for_questions(relation_questions.origin, related, teacher)
    with CaptureQueriesContext(connection) as relation_small_context:
        relation_small = teacher_client.get(relations_url, {'page': 1, 'page_size': 2})
    with CaptureQueriesContext(connection) as relation_large_context:
        relation_large = teacher_client.get(relations_url, {'page': 1, 'page_size': 6})

    assert relation_small.status_code == relation_large.status_code == 200
    assert len(relation_large_context) <= len(relation_small_context) + 2
