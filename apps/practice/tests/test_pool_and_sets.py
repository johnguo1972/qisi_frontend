import pytest
from rest_framework.test import APIClient

from apps.accounts.models import StudentParentBind, UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.parser.models import ExamQuestion
from apps.practice.models import PracticeAttempt, PracticePoolItem, PracticeSet
from apps.wrongbook.models import WrongBookItem


def visible_question(paper, no, *, difficulty=3, points=None, subject='数学'):
    return ExamQuestion.objects.create(
        paper=paper,
        question_no=no,
        question_type='single_choice',
        subject=subject,
        stem=f'精练测试题 {no}',
        difficulty=difficulty,
        knowledge_points=points or ['速度'],
        review_status='confirmed',
        need_review=False,
        tags=['测试'],
    )


def parent_client_for(parent, student):
    from django.core.cache import cache

    StudentParentBind.objects.create(
        student_user_id=student,
        parent_user_id=parent,
        relation_type='guardian',
        bind_status='active',
    )
    cache.set(f'parent_context:{parent.id}', str(student.id), timeout=300)
    client = APIClient()
    token = generate_tokens(parent, 'parent')['access_token']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.mark.django_db
def test_pool_add_revalidates_candidates_is_idempotent_and_supports_soft_delete(
    student_client, student_user, sample_paper
):
    original = visible_question(sample_paper, 'original')
    candidate = visible_question(sample_paper, 'candidate')
    wrong_item = WrongBookItem.objects.create(student_user_id=student_user, question_id=original.id)
    payload = {
        'items': [{
            'question_id': str(candidate.id),
            'source_wrong_item_id': str(wrong_item.id),
            'source_type': 'recommended_variant',
        }]
    }

    response = student_client.post('/api/v1/practice/pool/items/', payload, format='json')
    assert response.status_code == 201
    assert response.json()['meta']['added_count'] == 1
    pool_item = PracticePoolItem.objects.get(student_user=student_user, question_id=candidate.id)
    assert pool_item.recommendation_snapshot['algorithm_version'] == 'wrongbook-candidate-v1'

    duplicate = student_client.post('/api/v1/practice/pool/items', payload, format='json')
    assert duplicate.status_code == 201
    assert duplicate.json()['data'][0]['status'] == 'already_exists'
    assert PracticePoolItem.objects.filter(student_user=student_user, question_id=candidate.id).count() == 1

    removed = student_client.delete(f'/api/v1/practice/pool/items/{pool_item.id}/')
    assert removed.status_code == 200
    assert removed.json()['data']['status'] == 'removed'
    assert PracticePoolItem.objects.get(pk=pool_item.id).status == 'removed'

    restored = student_client.post('/api/v1/practice/pool/items/', payload, format='json')
    assert restored.status_code == 201
    assert restored.json()['data'][0]['status'] == 'restored'
    assert PracticePoolItem.objects.get(pk=pool_item.id).status == 'active'


@pytest.mark.django_db
def test_pool_add_rejects_forged_or_cross_student_questions_atomically(
    student_client, student_user, sample_paper
):
    original = visible_question(sample_paper, 'original')
    valid_candidate = visible_question(sample_paper, 'valid')
    forged_candidate = visible_question(sample_paper, 'wrong-subject', subject='物理')
    wrong_item = WrongBookItem.objects.create(student_user_id=student_user, question_id=original.id)
    payload = {
        'items': [
            {
                'question_id': str(valid_candidate.id),
                'source_wrong_item_id': str(wrong_item.id),
                'source_type': 'recommended_variant',
            },
            {
                'question_id': str(forged_candidate.id),
                'source_wrong_item_id': str(wrong_item.id),
                'source_type': 'recommended_variant',
            },
        ]
    }

    response = student_client.post('/api/v1/practice/pool/items/', payload, format='json')

    assert response.status_code == 400
    assert response.json()['data']['error_code'] == 'RECOMMENDATION_INVALID'
    assert PracticePoolItem.objects.filter(student_user=student_user).count() == 0


@pytest.mark.django_db
def test_pool_batch_remove_is_scoped_and_returns_removed_items(student_client, student_user, sample_paper):
    questions = [visible_question(sample_paper, str(index)) for index in range(2)]
    pool_items = [PracticePoolItem.objects.create(
        student_user=student_user,
        question_id=question.id,
        source_type='original_wrong',
        display_snapshot={'id': str(question.id)},
    ) for question in questions]

    response = student_client.post(
        '/api/v1/practice/pool/items/batch-remove/',
        {'item_ids': [str(item.id) for item in pool_items]},
        format='json',
    )

    assert response.status_code == 200
    assert response.json()['meta'] == {'removed_count': 2, 'requested_count': 2}
    assert not PracticePoolItem.objects.filter(student_user=student_user, status='active').exists()


@pytest.mark.django_db
def test_practice_set_preserves_request_order_validates_pool_ownership_and_tracks_progress(
    student_client, student_user, sample_paper
):
    questions = [visible_question(sample_paper, str(index)) for index in range(2)]
    pool_items = [PracticePoolItem.objects.create(
        student_user=student_user,
        question_id=question.id,
        source_type='recommended_variant',
        display_snapshot={'question_no': question.question_no},
    ) for question in questions]

    response = student_client.post(
        '/api/v1/practice/sets/',
        {
            'title': '顺序测试',
            'status': 'draft',
            'pool_item_ids': [str(pool_items[1].id), str(pool_items[0].id)],
        },
        format='json',
    )

    assert response.status_code == 201
    data = response.json()['data']
    assert data['question_count'] == 2
    assert [item['sort_no'] for item in data['items']] == [1, 2]
    assert [item['question_id'] for item in data['items']] == [
        str(questions[1].id), str(questions[0].id)
    ]
    practice_set = PracticeSet.objects.get(pk=data['id'])

    activate = student_client.post(f'/api/v1/practice/sets/{practice_set.id}/activate/', {}, format='json')
    assert activate.status_code == 200
    assert activate.json()['data']['status'] == 'active'

    first_item = practice_set.items.order_by('sort_no').first()
    PracticeAttempt.objects.create(
        practice_set=practice_set,
        set_item=first_item,
        student_user=student_user,
        answer_content={'value': 'A'},
        status='submitted',
    )
    detail = student_client.get(f'/api/v1/practice/sets/{practice_set.id}/')
    assert detail.status_code == 200
    assert detail.json()['data']['answered_count'] == 1
    assert float(detail.json()['data']['progress_percent']) == 50.0

    incomplete = student_client.post(f'/api/v1/practice/sets/{practice_set.id}/submit/', {}, format='json')
    assert incomplete.status_code == 400
    assert incomplete.json()['data']['error_code'] == 'PRACTICE_SET_INCOMPLETE'

    second_item = practice_set.items.order_by('sort_no').last()
    PracticeAttempt.objects.create(
        practice_set=practice_set,
        set_item=second_item,
        student_user=student_user,
        answer_content={'value': 'B'},
        status='graded',
    )
    completed = student_client.post(f'/api/v1/practice/sets/{practice_set.id}/submit/', {}, format='json')
    assert completed.status_code == 200
    assert completed.json()['data']['status'] == 'completed'


@pytest.mark.django_db
def test_parent_creates_set_for_selected_effective_student(student_user, sample_paper):
    parent = UserAccount.objects.create(
        role_type='parent', mobile='13900000888', display_name='测试家长', status='active'
    )
    grant_user_role(parent, 'parent')
    client = parent_client_for(parent, student_user)
    question = visible_question(sample_paper, '1')
    pool_item = PracticePoolItem.objects.create(
        student_user=student_user,
        question_id=question.id,
        source_type='original_wrong',
        display_snapshot={'question_no': '1'},
    )

    response = client.post(
        '/api/v1/practice/sets/',
        {'pool_item_ids': [str(pool_item.id)], 'title': '家长创建'},
        format='json',
    )

    assert response.status_code == 201
    practice_set = PracticeSet.objects.get(pk=response.json()['data']['id'])
    assert practice_set.student_user_id == student_user.id
    assert practice_set.created_by_user_id == parent.id
    assert practice_set.created_via_role == 'parent'
