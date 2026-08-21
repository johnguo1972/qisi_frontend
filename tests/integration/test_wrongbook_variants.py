import pytest

from apps.parser.models import ExamQuestion
from apps.wrongbook.models import WrongBookItem


@pytest.mark.django_db
def test_variant_submit_rejects_question_from_another_source(
    student_client, student_user, sample_paper
):
    original = ExamQuestion.objects.create(
        paper=sample_paper,
        question_no='original',
        question_type='single_choice',
        subject='数学',
        stem='原错题',
        answer='A',
        difficulty=3,
        knowledge_points=[],
    )
    candidate = ExamQuestion.objects.create(
        paper=sample_paper,
        question_no='candidate',
        question_type='single_choice',
        subject='数学',
        stem='同类题',
        answer=r'$\mathrm{B}$',
        difficulty=3,
        knowledge_points=[],
    )
    unrelated = ExamQuestion.objects.create(
        paper=sample_paper,
        question_no='unrelated',
        question_type='single_choice',
        subject='英语',
        stem='无关题',
        answer='C',
        difficulty=1,
        knowledge_points=[],
    )
    item = WrongBookItem.objects.create(
        student_user_id=student_user,
        question_id=original.id,
    )

    rejected = student_client.post(
        f'/api/v1/student/wrong-book/{item.id}/variant-submit/',
        {'question_id': str(unrelated.id), 'answer_content': {'selected_options': ['C']}},
        format='json',
    )

    assert rejected.status_code == 404
    assert rejected.json()['message'] == '题目不是该错题的同类题'

    accepted = student_client.post(
        f'/api/v1/student/wrong-book/{item.id}/variant-submit/',
        {'question_id': str(candidate.id), 'answer_content': {'selected_options': ['B']}},
        format='json',
    )

    assert accepted.status_code == 200
    assert accepted.json()['data']['is_correct'] is True


@pytest.mark.django_db
def test_variant_submit_accepts_text_for_legacy_unknown_fill_blank(
    student_client, student_user, sample_paper
):
    original = ExamQuestion.objects.create(
        paper=sample_paper,
        question_no='original-fill',
        question_type='single_choice',
        subject='物理',
        stem='原错题',
        answer='A',
        difficulty=3,
        knowledge_points=[],
    )
    variant = ExamQuestion.objects.create(
        paper=sample_paper,
        question_no='unknown-fill',
        question_type='unknown',
        subject='物理',
        stem=r'填写 $\underline{\hspace{2cm}}$ 和 $\underline{\hspace{2cm}}$',
        answer='S\n正',
        difficulty=3,
        knowledge_points=[],
    )
    item = WrongBookItem.objects.create(
        student_user_id=student_user,
        question_id=original.id,
    )

    response = student_client.post(
        f'/api/v1/student/wrong-book/{item.id}/variant-submit/',
        {'question_id': str(variant.id), 'answer_content': {'text': 'S,正'}},
        format='json',
    )

    assert response.status_code == 200
    assert response.json()['data']['is_correct'] is True
    assert response.json()['data']['is_pending'] is False
