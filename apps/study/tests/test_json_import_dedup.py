import json
import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.papers.models import ExamPaper, ParseTask
from apps.parser.models import ExamQuestion, QuestionContentFingerprint
from apps.study.models import QuestionIngestionBatch


def _upload_json_package(client, filename, package, assets):
    archive = BytesIO()
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('all_questions.json', json.dumps(package, ensure_ascii=False))
        for name, content in assets.items():
            zf.writestr(f'assets/{name}', content)
    return client.post(
        '/api/v1/questions/import-json-package',
        {'file': SimpleUploadedFile(filename, archive.getvalue(), 'application/zip')},
        format='multipart',
    )


@pytest.mark.django_db
def test_json_import_deduplicates_equivalent_formula_assets_with_different_keys(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009201', display_name='JSON dedup teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    package = {
        'paper': {'title': 'Formula aliases', 'subject': 'math', 'grade': 'Grade 8'},
        'questions': [
            {
                'question_no': '1',
                'question_type': 'single_choice',
                'stem': 'Find [[formula:q001_formula_01]].',
                'options': [{'label': 'A', 'content': 'One'}],
                'formula_assets': [{'file': '../assets/q001_formula_01.png'}],
            },
            {
                'question_no': '2',
                'question_type': 'single_choice',
                'stem': 'Find [[formula:q002_formula_01]].',
                'options': [{'label': 'A', 'content': 'One'}],
                'formula_assets': [{'file': '../assets/q002_formula_01.png'}],
            },
        ],
    }

    response = _upload_json_package(
        client,
        'formula-aliases.zip',
        package,
        {
            'q001_formula_01.png': b'same-formula-image',
            'q002_formula_01.png': b'same-formula-image',
        },
    )

    assert response.status_code == 200
    assert response.data['code'] == 0
    assert response.data['data']['total_read'] == 2
    assert response.data['data']['imported'] == 1
    assert response.data['data']['skipped_in_package'] == 1
    assert response.data['data']['skipped_existing'] == 0
    assert response.data['data']['failed'] == 0
    assert ExamQuestion.objects.count() == 1
    assert QuestionContentFingerprint.objects.count() == 1
    batch = QuestionIngestionBatch.objects.get(actor=teacher)
    assert str(batch.paper_id) == response.data['data']['paper_id']
    assert batch.created_count == 1
    assert batch.skipped_in_package_count == 1


@pytest.mark.django_db
def test_all_existing_json_questions_create_no_paper_task_or_media_copy(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009202', display_name='Duplicate package teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    package = {
        'paper': {'title': 'Original package', 'subject': 'math', 'grade': 'Grade 8'},
        'questions': [{
            'question_no': '1',
            'question_type': 'single_choice',
            'stem': 'Choose [[formula:q001_formula_01]].',
            'options': [{'label': 'A', 'content': 'One'}],
            'formula_assets': [{'file': '../assets/q001_formula_01.png'}],
        }],
    }
    assets = {'q001_formula_01.png': b'formula-image'}

    first = _upload_json_package(client, 'original.zip', package, assets)
    assert first.status_code == 200
    paper_count = ExamPaper.objects.count()
    task_count = ParseTask.objects.count()
    media_paths = sorted(
        path.relative_to(settings.MEDIA_ROOT).as_posix()
        for path in settings.MEDIA_ROOT.rglob('*') if path.is_file()
    )

    duplicate = _upload_json_package(client, 'duplicates-only.zip', package, assets)

    assert duplicate.status_code == 200
    assert duplicate.data['code'] == 0
    assert duplicate.data['data']['paper_id'] is None
    assert duplicate.data['data']['total_read'] == 1
    assert duplicate.data['data']['imported'] == 0
    assert duplicate.data['data']['skipped_existing'] == 1
    assert duplicate.data['data']['skipped_in_package'] == 0
    assert duplicate.data['data']['failed'] == 0
    assert ExamPaper.objects.count() == paper_count
    assert ParseTask.objects.count() == task_count
    assert sorted(
        path.relative_to(settings.MEDIA_ROOT).as_posix()
        for path in settings.MEDIA_ROOT.rglob('*') if path.is_file()
    ) == media_paths
    batch = QuestionIngestionBatch.objects.filter(actor=teacher).latest('created_at')
    assert batch.paper_id is None
    assert batch.created_count == 0
    assert batch.skipped_existing_count == 1


@pytest.mark.django_db
def test_json_import_uses_source_image_bytes_to_distinguish_same_text_questions(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009203', display_name='Image hash teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    package = {
        'paper': {'title': 'Image hashes', 'subject': 'math', 'grade': 'Grade 8'},
        'questions': [
            {
                'question_no': '1',
                'question_type': 'single_choice',
                'stem': 'Read the diagram.',
                'options': [{'label': 'A', 'content': 'One'}],
                'illustrations': [{'file': '../assets/q001_stem.png'}],
            },
            {
                'question_no': '2',
                'question_type': 'single_choice',
                'stem': 'Read the diagram.',
                'options': [{'label': 'A', 'content': 'One'}],
                'illustrations': [{'file': '../assets/q002_stem.png'}],
            },
        ],
    }

    response = _upload_json_package(
        client,
        'different-diagrams.zip',
        package,
        {'q001_stem.png': b'first-diagram', 'q002_stem.png': b'second-diagram'},
    )

    assert response.status_code == 200
    assert response.data['data']['imported'] == 2
    assert response.data['data']['skipped_in_package'] == 0
    assert ExamQuestion.objects.count() == 2
    assert QuestionContentFingerprint.objects.count() == 2
