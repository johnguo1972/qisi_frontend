from pathlib import Path

import pytest
import fitz

from apps.parser.models import ExamQuestion
from apps.study.student_views import _build_pdf, _pdf_text_with_formulas
from apps.wrongbook.models import WrongBookItem


def test_variant_pdf_formula_text_is_rendered_without_raw_latex():
    rendered = _pdf_text_with_formulas(
        '选择 $\\\\mathrm{A}$，空格 $\\\\underline{\\\\hspace{2cm}}$。'
    )

    assert '\\mathrm' not in rendered
    assert '\\underline' not in rendered
    assert 'A' in rendered
    assert '_' in rendered


def test_variant_pdf_output_does_not_contain_raw_latex_commands():
    slash = chr(92)
    pdf_bytes = _build_pdf(
        'variants',
        [{
            'id': 'q1',
            'question_type': 'unknown',
            'stem': f'选择 ${slash}mathrm{{A}}$，空格 ${slash}underline{{{slash}hspace{{2cm}}}}$。',
            'options_html': [],
            'image_urls': [],
        }],
        False,
        render_formulas=True,
    )

    document = fitz.open(stream=pdf_bytes, filetype='pdf')
    text = ''.join(page.get_text() for page in document)
    assert f'{slash}mathrm' not in text
    assert f'{slash}underline' not in text
    assert 'A' in text
    assert '\u586b\u7a7a\u9898' in text


@pytest.mark.django_db
def test_student_can_export_legacy_variant_questions_by_question_ids(
    student_client, student_user, sample_paper, settings, tmp_path
):
    settings.MEDIA_ROOT = Path(tmp_path)
    original = ExamQuestion.objects.create(
        paper=sample_paper, question_no='original', question_type='single_choice',
        subject='数学', stem='原错题', answer='A', difficulty=3, knowledge_points=[],
    )
    variants = [
        ExamQuestion.objects.create(
            paper=sample_paper, question_no=f'variant-{index}', question_type='single_choice',
            subject='数学', stem=f'关联题{index}', answer='B', difficulty=3, knowledge_points=[],
        )
        for index in range(1, 4)
    ]
    wrong_item = WrongBookItem.objects.create(
        student_user_id=student_user, question_id=original.id,
    )

    response = student_client.post(
        '/api/v1/student/export/pdf',
        {
            'export_type': 'variants',
            'source_wrong_item_id': str(wrong_item.id),
            'item_ids': [str(question.id) for question in variants],
            'include_answers': False,
        },
        format='json',
    )

    assert response.status_code == 200
    data = response.json()['data']
    assert data['question_count'] == 3
    output_path = Path(settings.MEDIA_ROOT) / data['download_url'].replace('/media/', '')
    assert output_path.exists()
    assert output_path.read_bytes().startswith(b'%PDF')

    legacy_response = student_client.post(
        '/api/v1/student/export/pdf',
        {
            'export_type': 'wrongbook',
            'item_ids': [str(original.id)],
            'include_answers': False,
        },
        format='json',
    )
    assert legacy_response.status_code == 200
    assert legacy_response.json()['data']['question_count'] == 1

    old_variants_page_response = student_client.post(
        '/api/v1/student/export/pdf',
        {
            'export_type': 'wrongbook',
            'item_ids': [str(question.id) for question in variants],
            'include_answers': False,
        },
        format='json',
    )
    assert old_variants_page_response.status_code == 200
    assert old_variants_page_response.json()['data']['question_count'] == 3


@pytest.mark.django_db
def test_variant_export_rejects_questions_not_in_selected_wrong_item_candidates(
    student_client, student_user, sample_paper
):
    original = ExamQuestion.objects.create(
        paper=sample_paper, question_no='original', question_type='single_choice',
        subject='数学', stem='原错题', answer='A', difficulty=3, knowledge_points=[],
    )
    unrelated = ExamQuestion.objects.create(
        paper=sample_paper, question_no='unrelated', question_type='single_choice',
        subject='英语', stem='无关题', answer='B', difficulty=1, knowledge_points=[],
    )
    wrong_item = WrongBookItem.objects.create(
        student_user_id=student_user, question_id=original.id,
    )

    response = student_client.post(
        '/api/v1/student/export/pdf',
        {
            'export_type': 'variants',
            'source_wrong_item_id': str(wrong_item.id),
            'item_ids': [str(unrelated.id)],
            'include_answers': False,
        },
        format='json',
    )

    assert response.status_code == 404
    assert response.json()['message'] == '未找到可导出的题目'
