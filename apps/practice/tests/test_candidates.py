import pytest

from apps.parser.models import ExamQuestion
from apps.practice.models import (
    PracticeAttempt,
    PracticeAttemptImage,
    PracticePoolItem,
    PracticeSet,
    PracticeSetItem,
)
from apps.practice.recommendation import (
    knowledge_point_keys,
    normalize_difficulty_star,
    normalize_knowledge_points,
    normalize_tags,
)
from apps.wrongbook.models import WrongBookItem


def make_question(paper, *, no, subject='数学', difficulty=3, points=None, stage=None, **kwargs):
    if stage is not None:
        paper.stage = stage
        paper.save(update_fields=['stage'])
    values = {
        'paper': paper,
        'question_no': no,
        'question_type': 'single_choice',
        'subject': subject,
        'stem': f'测试题干 {no}',
        'difficulty': difficulty,
        'knowledge_points': points,
        'review_status': 'confirmed',
        'need_review': False,
        'tags': kwargs.pop('tags', []),
    }
    values.update(kwargs)
    return ExamQuestion.objects.create(**values)


@pytest.mark.django_db
def test_candidate_endpoint_applies_strict_stage_subject_kp_and_difficulty(
    student_client, student_user, sample_paper
):
    original = make_question(
        sample_paper,
        no='original',
        difficulty=3,
        points=[{'id': 'kp-1', 'module': '力学', 'name': '速度'}, {'module': '图像', 'name': '路程'}],
    )
    same = make_question(
        sample_paper, no='same', difficulty=3,
        points=[{'id': 'kp-1', 'module': '力学'}, {'module': '图像'}], tags=['易错题', '易错题'],
    )
    harder = make_question(
        sample_paper, no='harder', difficulty=4,
        points=[{'id': 'kp-1', 'module': '力学'}, {'module': '图像'}],
    )
    easier = make_question(
        sample_paper, no='easier', difficulty=2,
        points=[{'id': 'kp-1', 'module': '力学'}, {'module': '图像'}],
    )
    make_question(sample_paper, no='only-one-kp', difficulty=3, points=[{'id': 'kp-1'}])
    make_question(sample_paper, no='too-hard', difficulty=5, points=[{'id': 'kp-1'}, {'module': '图像'}])
    make_question(sample_paper, no='wrong-subject', difficulty=3, subject='物理', points=[{'id': 'kp-1'}, {'module': '图像'}])
    make_question(sample_paper, no='wrong-kp', difficulty=3, points=[{'id': 'other-1'}, {'module': 'other-2'}])
    make_question(sample_paper, no='unreviewed', difficulty=3, points=[{'id': 'kp-1'}, {'module': '图像'}], review_status='unreviewed')
    make_question(sample_paper, no='bad-stem', difficulty=3, points=[{'id': 'kp-1'}, {'module': '图像'}], stem='')

    high_paper = type(sample_paper).objects.create(
        title='高中试卷', subject='数学', stage='高中', source_file_path='high.docx', uploaded_by=sample_paper.uploaded_by
    )
    make_question(high_paper, no='wrong-stage', difficulty=3, points=[{'id': 'kp-1'}, {'module': '图像'}])
    wrong_item = WrongBookItem.objects.create(student_user_id=student_user, question_id=original.id)

    response = student_client.get(f'/api/v1/practice/wrong-book/{wrong_item.id}/candidates/')

    assert response.status_code == 200
    body = response.json()
    assert body['code'] == 0
    assert [item['question_no'] for item in body['data']] == ['same', 'harder', 'easier']
    assert body['meta']['stage'] == '初中'
    assert body['meta']['returned_count'] == 3
    assert body['meta']['insufficient_reason'] is None
    assert body['data'][0]['question_type_label'] == '单选题'
    assert body['data'][0]['difficulty_label'] == '中等'
    assert body['data'][0]['knowledge_point_labels'] == ['力学', '图像']
    assert body['data'][0]['tags'] == ['易错题']
    assert body['data'][0]['match']['matched_knowledge_point_count'] == 2
    assert body['data'][0]['match']['difficulty_match'] == 'same'
    assert body['data'][1]['match']['difficulty_match'] == 'slightly_harder'
    assert body['data'][2]['match']['difficulty_match'] == 'slightly_easier'
    assert 'answer' not in body['data'][0]
    assert 'analysis' not in body['data'][0]


@pytest.mark.django_db
def test_candidate_endpoint_excludes_active_pool_items_and_does_not_pad_invalid_results(
    student_client, student_user, sample_paper
):
    original = make_question(sample_paper, no='original', difficulty=3, points=['速度'])
    pooled = make_question(sample_paper, no='pooled', difficulty=3, points=['速度'])
    available = make_question(sample_paper, no='available', difficulty=4, points=['速度'])
    PracticePoolItem.objects.create(
        student_user=student_user,
        question_id=pooled.id,
        source_type='recommended_variant',
        display_snapshot={'id': str(pooled.id)},
        status='active',
    )
    wrong_item = WrongBookItem.objects.create(student_user_id=student_user, question_id=original.id)

    response = student_client.get(f'/api/v1/practice/wrong-book/{wrong_item.id}/candidates/')

    assert response.status_code == 200
    body = response.json()
    assert [item['question_no'] for item in body['data']] == ['available']
    assert body['meta']['returned_count'] == 1
    assert body['meta']['recommendation_mode'] == 'knowledge_point_match'


@pytest.mark.django_db
def test_candidate_endpoint_falls_back_when_original_has_no_knowledge_points(
    student_client, student_user, sample_paper
):
    original = make_question(
        sample_paper, no='original-no-kp', difficulty=3, points=[],
        question_type='multiple_choice', subject='物理',
    )
    make_question(
        sample_paper, no='fallback-candidate', difficulty=3, points=[],
        question_type='multiple_choice', subject='物理',
    )
    wrong_item = WrongBookItem.objects.create(student_user_id=student_user, question_id=original.id)

    response = student_client.get(f'/api/v1/practice/wrong-book/{wrong_item.id}/candidates/')

    assert response.status_code == 200
    body = response.json()
    assert [item['question_no'] for item in body['data']] == ['fallback-candidate']
    assert body['meta']['recommendation_mode'] == 'metadata_fallback'
    assert body['data'][0]['match']['same_question_type'] is True
    assert '不足3道' in body['meta']['insufficient_reason']


@pytest.mark.django_db
def test_candidate_endpoint_reports_missing_original_metadata_without_relaxing_rules(
    student_client, student_user, sample_paper
):
    original = make_question(sample_paper, no='original', difficulty=None, points=['速度'])
    make_question(sample_paper, no='candidate', difficulty=3, points=['速度'])
    wrong_item = WrongBookItem.objects.create(student_user_id=student_user, question_id=original.id)

    response = student_client.get(f'/api/v1/practice/wrong-book/{wrong_item.id}/candidates/')

    assert response.status_code == 200
    body = response.json()
    assert body['data'] == []
    assert '原题难度缺失' in body['meta']['insufficient_reason']
    assert '不足3道' in body['meta']['insufficient_reason']


@pytest.mark.django_db
def test_candidate_endpoint_accepts_legacy_question_id_path_parameter(
    student_client, student_user, sample_paper
):
    original = make_question(sample_paper, no='legacy-original', difficulty=3, points=['速度'])
    make_question(sample_paper, no='legacy-candidate', difficulty=3, points=['速度'])
    WrongBookItem.objects.create(student_user_id=student_user, question_id=original.id)

    response = student_client.get(
        f'/api/v1/practice/wrong-book/{original.id}/candidates/'
    )

    assert response.status_code == 200
    assert response.json()['data'][0]['question_no'] == 'legacy-candidate'


@pytest.mark.django_db
def test_candidate_endpoint_is_scoped_to_the_effective_student(student_client, student_user, sample_paper):
    from django.contrib.auth import get_user_model

    other = get_user_model().objects.create(
        role_type='student', mobile='13900000999', display_name='其他学生', status='active'
    )
    original = make_question(sample_paper, no='original', difficulty=3, points=['速度'])
    make_question(sample_paper, no='candidate', difficulty=3, points=['速度'])
    other_item = WrongBookItem.objects.create(student_user_id=other, question_id=original.id)

    response = student_client.get(f'/api/v1/practice/wrong-book/{other_item.id}/candidates/')

    assert response.status_code == 404
    assert response.json()['data'] == []


def test_candidate_metadata_normalizers_handle_historical_values():
    assert normalize_difficulty_star('L3') == 3
    assert normalize_difficulty_star('3.4') == 3
    assert normalize_difficulty_star('not-a-level') is None
    assert normalize_knowledge_points({'points': ['速度', {'id': 'kp-1'}]}) == [
        {'name': '速度'}, {'id': 'kp-1'}
    ]
    assert knowledge_point_keys(['速度', {'module': '力学'}]) == {'name:速度', 'module:力学'}
    assert normalize_tags(['易错题', '', '易错题', '期末']) == ['易错题', '期末']


@pytest.mark.django_db
def test_practice_models_keep_pool_set_attempt_and_image_snapshots(student_user, sample_paper):
    question = make_question(sample_paper, no='1', points=['速度'])
    wrong_item = WrongBookItem.objects.create(student_user_id=student_user, question_id=question.id)
    pool_item = PracticePoolItem.objects.create(
        student_user=student_user,
        question_id=question.id,
        source_wrong_item=wrong_item,
        source_type='recommended_variant',
        recommendation_snapshot={'algorithm_version': 'wrongbook-candidate-v1'},
        display_snapshot={'stem': question.stem},
    )
    practice_set = PracticeSet.objects.create(
        student_user=student_user,
        created_by_user=student_user,
        created_via_role='student',
        title='测试精练',
        question_count=1,
    )
    set_item = PracticeSetItem.objects.create(
        practice_set=practice_set,
        pool_item=pool_item,
        question_id=question.id,
        sort_no=1,
        source_type='recommended_variant',
        display_snapshot={'stem': question.stem},
    )
    attempt = PracticeAttempt.objects.create(
        practice_set=practice_set,
        set_item=set_item,
        student_user=student_user,
        answer_content={'value': 'A'},
        status='submitted',
    )
    image = PracticeAttemptImage.objects.create(
        attempt=attempt,
        student_user=student_user,
        image_path='practice/answer.jpg',
        page_no=1,
    )

    assert pool_item.source_wrong_item_id == wrong_item.id
    assert set_item.question_id == question.id
    assert attempt.answer_content == {'value': 'A'}
    assert image.attempt_id == attempt.id
