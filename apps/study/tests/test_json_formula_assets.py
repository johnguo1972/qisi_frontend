import json
import zipfile
from io import BytesIO
from io import StringIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.papers.models import ExamPaper
from apps.papers.models import ParseTask
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption
from apps.study import json_import_views
from apps.study.formula_assets import render_formula_placeholders
from apps.study.serializers import QuestionListSerializer


def test_formula_placeholder_is_replaced_with_inline_browser_image():
    html, missing = render_formula_placeholders(
        '矩形[[formula:q021_formula_01]]的边长',
        {'q021_formula_01': '/media/exams/json_imports/paper/formula.png'},
    )

    assert missing == []
    assert '[[formula:' not in html
    assert 'src="/media/exams/json_imports/paper/formula.png"' in html
    assert 'data-formula-key="q021_formula_01"' in html


def test_formula_placeholder_keeps_missing_token_visible_for_review():
    html, missing = render_formula_placeholders(
        '缺失[[formula:q999_formula_01]]',
        {},
    )

    assert html == '缺失[[formula:q999_formula_01]]'
    assert missing == ['q999_formula_01']


@pytest.mark.django_db
def test_json_import_converts_wmf_and_builds_formula_ready_html(tmp_path, settings, monkeypatch):
    assets_dir = tmp_path / 'assets'
    assets_dir.mkdir()
    (assets_dir / 'q001_formula_01.wmf').write_bytes(b'wmf-source')
    settings.MEDIA_ROOT = tmp_path / 'media'
    paper = ExamPaper.objects.create(
        title='Formula paper',
        subject='math',
        stage='junior',
        source_file_path='formula.zip',
    )

    def fake_convert(source, destination):
        output = destination.with_suffix('.png')
        output.write_bytes(b'png-output')
        return output

    monkeypatch.setattr(json_import_views, 'convert_formula_asset', fake_convert)

    question = json_import_views._import_single_question(
        {
            'question_no': '1',
            'question_type': 'single_choice',
            'stem': '边长为[[formula:q001_formula_01]]',
            'options': [
                {'label': 'A', 'content': '选项[[formula:q001_formula_01]]'},
            ],
            'formula_assets': [
                {'file': '../assets/q001_formula_01.wmf'},
            ],
        },
        paper,
        assets_dir,
        tmp_path,
    )

    question.refresh_from_db()
    option = question.options.get(option_label='A')
    formula_image = question.images.get(image_type='formula')
    assert '[[formula:' not in question.stem_html
    assert '/media/' in question.stem_html
    assert 'q001_formula_01' in question.stem_html
    assert '[[formula:' not in option.content_html
    assert formula_image.file_path.endswith('.png')
    assert formula_image.original_file_path.endswith('.wmf')
    assert question.formula_need_review is False
    payload = QuestionListSerializer(question).data
    assert payload['stem_html'] == question.stem_html
    assert payload['options'][0]['content_html'] == option.content_html


@pytest.mark.django_db
def test_page_upload_imports_formula_package_with_browser_ready_fields(
    tmp_path, settings, monkeypatch
):
    settings.MEDIA_ROOT = tmp_path / 'media'
    user = UserAccount.objects.create(
        role_type='teacher',
        mobile='13800009991',
        display_name='公式导入教师',
    )
    package = {
        'paper': {'title': '页面公式导入测试', 'subject': '数学', 'grade': '九年级'},
        'questions': [{
            'question_no': '1',
            'question_type': 'single_choice',
            'stem': '题干[[formula:q001_formula_01]]',
            'options': [{'label': 'A', 'content': '选项[[formula:q001_formula_01]]'}],
            'answer': {'raw': '答案[[formula:q001_formula_01]]'},
            'analysis': '解析[[formula:q001_formula_01]]',
            'formula_assets': [{'file': '../assets/q001_formula_01.wmf'}],
        }],
    }
    archive = BytesIO()
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('all_questions.json', json.dumps(package, ensure_ascii=False))
        zf.writestr('assets/q001_formula_01.wmf', b'wmf-source')

    def fake_convert(source, destination):
        output = destination.with_suffix('.png')
        output.write_bytes(b'png-output')
        return output

    monkeypatch.setattr(json_import_views, 'convert_formula_asset', fake_convert)
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        '/api/v1/questions/import-json-package',
        {'file': SimpleUploadedFile('formula-package.zip', archive.getvalue(), 'application/zip')},
        format='multipart',
    )

    assert response.status_code == 200
    assert response.data['code'] == 0
    assert response.data['data']['imported'] == 1
    assert response.data['data']['errors'] == 0
    question = ExamQuestion.objects.get(paper_id=response.data['data']['paper_id'])
    option = question.options.get(option_label='A')
    formula_image = question.images.get(image_type='formula')
    assert '[[formula:' not in question.stem_html
    assert '[[formula:' not in option.content_html
    assert '[[formula:' not in question.answer
    assert '[[formula:' not in question.analysis
    assert formula_image.file_path.endswith('.png')
    assert formula_image.original_file_path.endswith('.wmf')
    assert ParseTask.objects.get(paper=question.paper).status == 'success'


@pytest.mark.django_db
def test_page_upload_preserves_standard_latex_commands(tmp_path, settings):
    """The real multipart page upload must not consume JSON LaTeX escapes."""
    settings.MEDIA_ROOT = tmp_path / 'media'
    user = UserAccount.objects.create(
        role_type='teacher',
        mobile='13800009992',
        display_name='LaTeX导入教师',
    )
    roman_stem = (
        '以下哪个数值最接近（ ）\n'
        '$\\mathrm{A}$. $100$ 张\n'
        '$\\mathrm{B}$. $500$ 张'
    )
    blank_stem = (
        '请补充空缺：① $\\underline{\\hspace{2cm}}$；'
        '② $\\underline{\\hspace{2cm}}$。'
    )
    package = {
        'paper': {'title': '页面LaTeX导入测试', 'subject': '物理', 'grade': '九年级'},
        'questions': [
            {
                'question_no': '1',
                'question_type': 'single_choice',
                'stem': roman_stem,
                'options': [
                    {'label': 'A', 'content': '$\\mathrm{A}$. $100$ 张'},
                    {'label': 'B', 'content': '$\\mathrm{B}$. $500$ 张'},
                ],
            },
            {
                'question_no': '2',
                'question_type': 'fill_blank',
                'stem': blank_stem,
            },
        ],
    }
    archive = BytesIO()
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('all_questions.json', json.dumps(package, ensure_ascii=False))

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        '/api/v1/questions/import-json-package',
        {'file': SimpleUploadedFile('latex-package.zip', archive.getvalue(), 'application/zip')},
        format='multipart',
    )

    assert response.status_code == 200
    assert response.data['code'] == 0
    assert response.data['data']['imported'] == 2
    assert response.data['data']['errors'] == 0

    questions = {
        question.question_no: question
        for question in ExamQuestion.objects.filter(
            paper_id=response.data['data']['paper_id']
        ).prefetch_related('options')
    }
    assert questions['1'].stem == roman_stem
    assert questions['1'].stem_html == roman_stem
    assert questions['1'].options.get(option_label='A').content == '$\\mathrm{A}$. $100$ 张'
    assert questions['1'].options.get(option_label='A').content_html == '$\\mathrm{A}$. $100$ 张'
    assert questions['2'].stem == blank_stem
    assert questions['2'].stem_html == blank_stem
    assert questions['1'].formula_need_review is False
    assert questions['2'].formula_need_review is False

    roman_payload = QuestionListSerializer(questions['1']).data
    blank_payload = QuestionListSerializer(questions['2']).data
    assert roman_payload['stem_html'] == roman_stem
    assert roman_payload['options'][0]['content_html'] == '$\\mathrm{A}$. $100$ 张'
    assert blank_payload['stem_html'] == blank_stem


@pytest.mark.django_db
def test_repair_command_backfills_existing_formula_placeholders(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / 'media'
    relative_path = 'exams/json_imports/paper/q009_formula_01.png'
    formula_path = settings.MEDIA_ROOT / relative_path
    formula_path.parent.mkdir(parents=True)
    formula_path.write_bytes(b'png-output')
    paper = ExamPaper.objects.create(
        title='Existing formula paper',
        subject='math',
        stage='junior',
        source_file_path='existing.zip',
    )
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no='9',
        question_type='single_choice',
        subject='math',
        stem='题干[[formula:q009_formula_01]]',
    )
    option = QuestionOption.objects.create(
        question=question,
        option_label='A',
        content='选项[[formula:q009_formula_01]]',
    )
    QuestionImage.objects.create(
        paper=paper,
        question=question,
        image_type='formula',
        file_path=relative_path,
        original_file_path=relative_path,
    )

    dry_run_output = StringIO()
    call_command(
        'repair_json_formula_assets',
        paper_id=str(paper.id),
        stdout=dry_run_output,
    )
    assert 'repaired=1' in dry_run_output.getvalue()
    question.refresh_from_db()
    assert question.stem_html is None

    call_command('repair_json_formula_assets', paper_id=str(paper.id), apply=True)

    question.refresh_from_db()
    option.refresh_from_db()
    assert '[[formula:' not in question.stem_html
    assert relative_path in question.stem_html
    assert '[[formula:' not in option.content_html
    assert question.formula_need_review is False
