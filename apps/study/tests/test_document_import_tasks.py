import pytest
from unittest.mock import Mock
from docx import Document
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from apps.accounts.models import UserAccount
from apps.common.ai.exceptions import AIResponseError
from apps.courses.models import Course
from apps.study import document_import_tasks as module
from apps.study.document_import_models import QuestionDocumentImportTask
from apps.study.document_import_service import ExtractedDocument, ExtractedQuestionFragment
from apps.study.models import QuestionIngestionBatch


def valid_question():
    return {
        'question_no': '1',
        'question_type': 'single_choice',
        'stem': 'Choose one.',
        'options': [{'label': 'A', 'content': 'One'}],
        'answer': 'A',
        'analysis': 'Only A is one.',
        'tables': [],
        'illustrations': [],
        'confidence': 0.9,
        'review_reason': '',
        'source': {'page_start': 1, 'page_end': 1},
    }


def _asset_question(question_no, asset_file):
    question = valid_question()
    question['question_no'] = question_no
    question['stem'] = f'Question {question_no} has a diagram.'
    question['illustrations'] = [{'file': asset_file}]
    return question


def _pdf_with_image(tmp_path):
    image_path = tmp_path / 'pdf-diagram.png'
    Image.new('RGB', (10, 10), color='black').save(image_path)
    document_path = tmp_path / 'questions.pdf'
    pdf = canvas.Canvas(str(document_path), pagesize=letter)
    pdf.drawString(72, 720, '1. PDF diagram question')
    pdf.drawImage(str(image_path), 72, 650, width=20, height=20)
    pdf.save()
    return document_path


def _docx_with_image(tmp_path):
    image_path = tmp_path / 'docx-diagram.png'
    Image.new('RGB', (10, 10), color='black').save(image_path)
    document_path = tmp_path / 'questions.docx'
    document = Document()
    document.add_paragraph('1. DOCX diagram question')
    document.add_picture(str(image_path))
    document.save(document_path)
    return document_path


@pytest.fixture
def task(db):
    teacher = UserAccount.objects.create(
        mobile='13900008302', display_name='Document task teacher', role_type='teacher',
    )
    course = Course.objects.create(
        name='Document task course', subject='math', grade_level='Grade 8', teacher=teacher,
    )
    batch = QuestionIngestionBatch.objects.create(
        actor=teacher,
        course=course,
        source_type=QuestionIngestionBatch.SourceType.DOCUMENT_IMPORT,
        source_name='questions.pdf',
    )
    return QuestionDocumentImportTask.objects.create(
        batch=batch,
        course=course,
        source_file='imports/questions.pdf',
        detected_mime='application/pdf',
        document_type='pdf',
        page_count=2,
    )


@pytest.mark.django_db
def test_task_marks_partial_success_after_one_candidate_failure(task, monkeypatch):
    """One malformed Qwen candidate never prevents a valid sibling from importing."""
    monkeypatch.setattr(
        module,
        'extract_document',
        lambda _path: ExtractedDocument(
            document_type='pdf', page_count=2,
            fragments=[
                ExtractedQuestionFragment(question_no='1', text='1. Choose one.'),
                ExtractedQuestionFragment(question_no='2', text='2. Broken candidate.'),
            ],
        ),
    )
    monkeypatch.setattr(
        module,
        'structure_candidate',
        Mock(side_effect=[valid_question(), AIResponseError('bad json')]),
    )

    module.process_document_import_task.run(str(task.id))

    task.refresh_from_db()
    assert task.stage == 'partial_success'


@pytest.mark.django_db
@pytest.mark.parametrize('factory', [_pdf_with_image, _docx_with_image])
def test_document_asset_is_materialized_before_shared_ingestion(task, tmp_path, monkeypatch, factory):
    """PDF and DOCX internal images become readable source-root files and QuestionImages."""
    source_path = factory(tmp_path)
    task.source_file = str(source_path)
    task.document_type = source_path.suffix.lstrip('.')
    task.save(update_fields=['source_file', 'document_type'])

    def structure(candidate, *, asset_files=None):
        assert asset_files
        return _asset_question(candidate.question_no, next(iter(asset_files.values())))

    monkeypatch.setattr(module, 'structure_candidate', structure)

    module.process_document_import_task.run(str(task.id))

    task.refresh_from_db()
    from apps.parser.models import QuestionImage
    image = QuestionImage.objects.get()
    assert task.stage == 'success'
    assert image.file_path
    assert image.original_file_path


@pytest.mark.django_db
def test_task_continues_after_exhausted_asset_read_retry(task, monkeypatch):
    """A candidate that still raises OSError after its own retry does not stop later candidates."""
    monkeypatch.setattr(
        module,
        'extract_document',
        lambda _path: ExtractedDocument(
            document_type='pdf', page_count=3,
            fragments=[
                ExtractedQuestionFragment(question_no='1', text='1. First.'),
                ExtractedQuestionFragment(question_no='2', text='2. Asset failure.'),
                ExtractedQuestionFragment(question_no='3', text='3. Last.'),
            ],
        ),
    )
    third = valid_question()
    third['question_no'] = '3'
    monkeypatch.setattr(
        module,
        'structure_candidate',
        Mock(side_effect=[valid_question(), OSError(r'C:\private\asset.png unavailable'), third]),
    )

    module.process_document_import_task.run(str(task.id))

    task.refresh_from_db()
    assert task.stage == 'partial_success'
    assert task.progress == 100
    assert '[path hidden]' in task.error_summary
