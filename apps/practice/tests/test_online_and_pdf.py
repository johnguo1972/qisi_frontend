from pathlib import Path

import pytest

from apps.parser.models import ExamQuestion
from apps.practice.models import PracticeAttempt, PracticeSet, PracticeSetItem
from apps.practice.pdf_service import practice_pdf_questions
from apps.wrongbook.models import MasteryRecord, WrongBookItem
from apps.study.models import AnswerAttempt


def make_question(paper, no, *, question_type='single_choice', answer='A'):
    return ExamQuestion.objects.create(
        paper=paper,
        question_no=no,
        question_type=question_type,
        subject='数学',
        stem=f'在线精练题 {no}',
        answer=answer,
        analysis=f'解析 {no}',
        difficulty=3,
        knowledge_points=['速度'],
        review_status='confirmed',
        need_review=False,
    )


def make_active_set(student, paper, *, question_type='single_choice', answer='A'):
    question = make_question(paper, '1', question_type=question_type, answer=answer)
    practice_set = PracticeSet.objects.create(
        student_user=student,
        created_by_user=student,
        created_via_role='student',
        title='在线精练测试',
        status='active',
        question_count=1,
        pdf_version=1,
    )
    item = PracticeSetItem.objects.create(
        practice_set=practice_set,
        question_id=question.id,
        sort_no=1,
        source_type='recommended_variant',
        display_snapshot={
            'id': str(question.id),
            'question_no': question.question_no,
            'question_type': question.question_type,
            'question_type_label': '单选题',
            'difficulty': 3.0,
            'difficulty_label': '中等',
            'stage': '初中',
            'subject': '数学',
            'knowledge_points': [{'name': '速度'}],
            'knowledge_point_labels': ['速度'],
            'tags': [],
            'stem': question.stem,
            'stem_html': None,
            'images': [],
            'options': [],
        },
    )
    return practice_set, item, question


@pytest.mark.django_db
def test_online_objective_submit_is_isolated_and_updates_practice_progress(
    student_client, student_user, sample_paper
):
    practice_set, item, question = make_active_set(student_user, sample_paper)

    response = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/items/{item.id}/attempts/',
        {
            'question_id': str(question.id),
            'answer_content': {'selected_options': ['A']},
        },
        format='json',
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['is_correct'] is True
    assert data['is_pending'] is False
    assert data['score'] == 100.0
    assert data['student_answer'] == {'selected_options': ['A']}
    assert data['correct_answer'] == 'A'
    assert data['analysis'] == '解析 1'
    assert data['answered_count'] == 1
    assert data['progress_percent'] == 100.0
    assert PracticeAttempt.objects.filter(practice_set=practice_set).count() == 1
    assert AnswerAttempt.objects.filter(question_id=question.id).count() == 0
    assert WrongBookItem.objects.filter(student_user_id=student_user, question_id=question.id).count() == 0
    assert MasteryRecord.objects.filter(student_user_id=student_user).count() == 0

    questions = student_client.get(f'/api/v1/practice/sets/{practice_set.id}/questions')
    assert questions.status_code == 200
    assert questions.json()['data'][0]['latest_attempt']['is_correct'] is True
    assert questions.json()['data'][0]['latest_attempt']['student_answer'] == {'selected_options': ['A']}
    assert questions.json()['data'][0]['latest_attempt']['correct_answer'] == 'A'
    assert questions.json()['data'][0]['latest_attempt']['analysis'] == '解析 1'
    assert 'answer' not in questions.json()['data'][0]['display_snapshot']


@pytest.mark.django_db
def test_online_submit_validates_question_and_answer_shape(student_client, student_user, sample_paper):
    practice_set, item, question = make_active_set(student_user, sample_paper)

    mismatch = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/items/{item.id}/attempts/',
        {'question_id': str(practice_set.id), 'answer_content': {'selected_options': ['A']}},
        format='json',
    )
    assert mismatch.status_code == 400
    assert mismatch.json()['data']['error_code'] == 'QUESTION_MISMATCH'

    invalid_shape = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/items/{item.id}/attempts/',
        {'question_id': str(question.id), 'answer_content': {'selected_options': 'A'}},
        format='json',
    )
    assert invalid_shape.status_code == 400
    assert invalid_shape.json()['data']['error_code'] == 'INVALID_ANSWER_FORMAT'
    assert not PracticeAttempt.objects.filter(practice_set=practice_set).exists()


@pytest.mark.django_db
def test_online_subjective_submit_is_pending_and_does_not_create_wrongbook_entry(
    student_client, student_user, sample_paper
):
    practice_set, item, question = make_active_set(
        student_user, sample_paper, question_type='short_answer', answer='答案'
    )

    response = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/items/{item.id}/attempts/',
        {'question_id': str(question.id), 'answer_content': {'text': '我的作答'}},
        format='json',
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['is_correct'] is None
    assert data['is_pending'] is True
    assert data['status'] == 'pending_review'
    attempt = PracticeAttempt.objects.get(pk=data['attempt_id'])
    assert attempt.score is None
    assert not WrongBookItem.objects.filter(student_user_id=student_user, question_id=question.id).exists()


@pytest.mark.django_db
def test_parent_cannot_submit_online_practice(student_user, sample_paper):
    from apps.practice.tests.test_pool_and_sets import parent_client_for
    from apps.accounts.models import UserAccount
    from apps.accounts.roles import grant_user_role

    parent = UserAccount.objects.create(
        role_type='parent', mobile='13900000777', display_name='答题家长', status='active'
    )
    grant_user_role(parent, 'parent')
    client = parent_client_for(parent, student_user)
    practice_set, item, question = make_active_set(student_user, sample_paper)

    response = client.post(
        f'/api/v1/practice/sets/{practice_set.id}/items/{item.id}/attempts/',
        {'question_id': str(question.id), 'answer_content': {'selected_options': ['A']}},
        format='json',
    )

    assert response.status_code == 403
    assert not PracticeAttempt.objects.filter(practice_set=practice_set).exists()


@pytest.mark.django_db
def test_practice_pdf_uses_set_item_order_and_persists_download_path(
    student_client, student_user, sample_paper, settings, tmp_path
):
    settings.MEDIA_ROOT = Path(tmp_path)
    first = make_question(sample_paper, 'first')
    second = make_question(sample_paper, 'second')
    practice_set = PracticeSet.objects.create(
        student_user=student_user,
        created_by_user=student_user,
        created_via_role='student',
        title='PDF顺序测试',
        status='active',
        question_count=2,
        pdf_version=1,
    )
    for sort_no, question in [(1, first), (2, second)]:
        PracticeSetItem.objects.create(
            practice_set=practice_set,
            question_id=question.id,
            sort_no=sort_no,
            source_type='recommended_variant',
            display_snapshot={
                'id': str(question.id), 'question_no': question.question_no,
                'question_type': 'single_choice', 'stem': question.stem,
                'knowledge_points': [], 'images': [], 'options': [],
            },
        )

    pdf_questions = practice_pdf_questions(practice_set)
    assert [item['question_no'] for item in pdf_questions] == ['first', 'second']
    assert 'answer' not in pdf_questions[0]
    response = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/export-pdf/',
        {'include_answers': False, 'watermark_text': '测试'},
        format='json',
    )
    assert response.status_code == 200
    payload = response.json()['data']
    output_path = Path(settings.MEDIA_ROOT) / payload['pdf_file_path']
    assert output_path.exists()
    assert output_path.read_bytes().startswith(b'%PDF')
    assert practice_set.__class__.objects.get(pk=practice_set.id).pdf_file_path == payload['pdf_file_path']

    download = student_client.get(f'/api/v1/practice/sets/{practice_set.id}/pdf/')
    assert download.status_code == 200
    assert download.json()['data']['pdf_file_path'] == payload['pdf_file_path']

    answer_pdf = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/export-pdf/',
        {'include_answers': True},
        format='json',
    )
    assert answer_pdf.status_code == 200
    assert answer_pdf.json()['data']['pdf_file_path'].endswith('_answers.pdf')
    assert PracticeSet.objects.get(pk=practice_set.id).pdf_file_path == payload['pdf_file_path']

    from apps.accounts.models import UserAccount
    from apps.accounts.roles import grant_user_role
    from apps.practice.tests.test_pool_and_sets import parent_client_for

    parent = UserAccount.objects.create(
        role_type='parent', mobile='13900000666', display_name='PDF家长', status='active'
    )
    grant_user_role(parent, 'parent')
    parent_client = parent_client_for(parent, student_user)
    parent_pdf = parent_client.get(f'/api/v1/practice/sets/{practice_set.id}/pdf/')
    assert parent_pdf.status_code == 200
    assert not parent_pdf.json()['data']['pdf_file_path'].endswith('_answers.pdf')
