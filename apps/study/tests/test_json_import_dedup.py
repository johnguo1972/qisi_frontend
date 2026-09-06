import json
import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.papers.models import ExamPaper, ParseTask
from apps.parser.question_identity import build_content_fingerprint
from apps.parser.models import ExamQuestion, QuestionContentFingerprint
from apps.study import json_import_views
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


@pytest.mark.django_db
def test_json_import_returns_bounded_duplicate_details_with_canonical_question(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009204', display_name='Duplicate detail teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    package = {
        'paper': {'title': 'Duplicate details', 'subject': 'math', 'grade': 'Grade 8'},
        'questions': [
            {'question_no': '1', 'question_type': 'single_choice', 'stem': 'Same?',
             'options': [{'label': 'A', 'content': 'One'}]},
            {'question_no': '2', 'question_type': 'single_choice', 'stem': 'Same?',
             'options': [{'label': 'A', 'content': 'One'}]},
        ],
    }

    first = _upload_json_package(client, 'details-first.zip', package, {})
    assert first.status_code == 200
    canonical = ExamQuestion.objects.get()
    second = _upload_json_package(client, 'details-second.zip', package, {})

    details = second.data['data']['details']
    assert len(details) <= 20
    assert {detail['category'] for detail in details} == {'existing', 'in_package'}
    assert {detail['source_index'] for detail in details} == {0, 1}
    for detail in details:
        assert detail['existing_canonical_question_id'] == str(canonical.id)
        assert detail['existing_paper_id'] == str(canonical.paper_id)
        assert detail['summary'] == 'Same?'


@pytest.mark.django_db
def test_json_import_normalizes_common_question_type_and_preserves_source_type(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009205', display_name='Type normalization teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    response = _upload_json_package(client, 'types.zip', {
        'paper': {'title': 'Types', 'subject': 'math', 'grade': 'Grade 8'},
        'questions': [{
            'question_no': '1', 'question_type': 'calculation', 'stem': '计算 1 + 1',
            'answer': {'raw': '2'},
        }],
    }, {})

    assert response.status_code == 200
    question = ExamQuestion.objects.get()
    assert question.question_type == 'computation'
    assert question.source_question_type == 'calculation'


@pytest.mark.django_db
def test_json_import_rejects_unsupported_question_type_without_persisting_side_effects(
    tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009211', display_name='Unsupported type teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)

    response = _upload_json_package(client, 'unsupported-type.zip', {
        'paper': {'title': 'Unsupported type', 'subject': 'math', 'grade': 'Grade 8'},
        'questions': [{
            'question_no': '1',
            'question_type': 'not_a_supported_type',
            'stem': 'Unsupported type with no structural evidence.',
        }],
    }, {})

    assert response.status_code == 200
    assert response.data['code'] == 0
    assert response.data['data']['imported'] == 0
    assert response.data['data']['failed'] == 1
    assert response.data['data']['paper_id'] is None
    assert not ExamQuestion.objects.exists()
    assert not QuestionContentFingerprint.objects.filter(
        state=QuestionContentFingerprint.State.ACTIVE
    ).exists()
    assert response.data['data']['error_details'][0]['error'] == 'unsupported_question_type'


@pytest.mark.django_db
def test_corrupt_json_zip_creates_failed_ingestion_batch(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009206', display_name='Corrupt archive teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)

    response = client.post(
        '/api/v1/questions/import-json-package',
        {'file': SimpleUploadedFile('corrupt.zip', b'not a zip', 'application/zip')},
        format='multipart',
    )

    assert response.status_code == 500
    batch = QuestionIngestionBatch.objects.get(actor=teacher)
    assert batch.source_name == 'corrupt.zip'
    assert batch.status == QuestionIngestionBatch.Status.FAILED
    assert batch.failed_count == 1


@pytest.mark.django_db
def test_unsafe_json_zip_creates_failed_ingestion_batch(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009210', display_name='Unsafe archive teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    archive = BytesIO()
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('../outside.json', '{}')

    response = client.post(
        '/api/v1/questions/import-json-package',
        {'file': SimpleUploadedFile('unsafe.zip', archive.getvalue(), 'application/zip')},
        format='multipart',
    )

    assert response.status_code == 500
    batch = QuestionIngestionBatch.objects.get(actor=teacher)
    assert batch.source_name == 'unsafe.zip'
    assert batch.status == QuestionIngestionBatch.Status.FAILED
    assert batch.failed_count == 1


@pytest.mark.django_db
def test_missing_illustration_fails_preflight_without_creating_paper_or_task(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009207', display_name='Missing illustration teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    response = _upload_json_package(client, 'missing-image.zip', {
        'paper': {'title': 'Missing image', 'subject': 'math', 'grade': 'Grade 8'},
        'questions': [{
            'question_no': '1', 'question_type': 'single_choice', 'stem': 'Diagram?',
            'options': [{'label': 'A', 'content': 'One'}],
            'illustrations': [{'file': '../assets/not-present.png'}],
        }],
    }, {})

    assert response.status_code == 200
    assert response.data['data']['failed'] == 1
    assert response.data['data']['paper_id'] is None
    assert not ExamPaper.objects.exists()
    assert not ParseTask.objects.exists()


@pytest.mark.django_db
def test_reserving_fingerprint_is_failed_instead_of_reported_as_existing(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009208', display_name='Reservation teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    fingerprint = build_content_fingerprint(
        stem='Reserved?', options=['One'], formula_texts=[], image_hashes=[]
    )
    QuestionContentFingerprint.objects.create(fingerprint=fingerprint)
    response = _upload_json_package(client, 'reserving.zip', {
        'paper': {'title': 'Reserving', 'subject': 'math', 'grade': 'Grade 8'},
        'questions': [{
            'question_no': '1', 'question_type': 'single_choice', 'stem': 'Reserved?',
            'options': [{'label': 'A', 'content': 'One'}],
        }],
    }, {})

    assert response.status_code == 200
    assert response.data['data']['failed'] == 1
    assert response.data['data']['skipped_existing'] == 0
    assert response.data['data']['paper_id'] is None


@pytest.mark.django_db
def test_failed_json_import_removes_media_copied_before_database_rollback(
    tmp_path, settings, monkeypatch
):
    settings.MEDIA_ROOT = tmp_path / 'media'
    teacher = UserAccount.objects.create(
        mobile='13900009209', display_name='Media rollback teacher', role_type='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)

    def fail_activation(*_args):
        raise RuntimeError('registry activation failed')

    monkeypatch.setattr(json_import_views, 'activate_content_fingerprint', fail_activation)
    response = _upload_json_package(client, 'rollback-media.zip', {
        'paper': {'title': 'Media rollback', 'subject': 'math', 'grade': 'Grade 8'},
        'questions': [{
            'question_no': '1', 'question_type': 'single_choice', 'stem': 'Diagram?',
            'options': [{'label': 'A', 'content': 'One'}],
            'illustrations': [{'file': '../assets/diagram.png'}],
        }],
    }, {'diagram.png': b'diagram'})

    assert response.status_code == 200
    assert response.data['data']['failed'] == 1
    assert not ExamQuestion.objects.exists()
    import_root = settings.MEDIA_ROOT / 'exams' / 'json_imports'
    assert not import_root.exists() or not list(import_root.rglob('*'))
