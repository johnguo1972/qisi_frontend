from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from docx import Document

from apps.study.document_import_service import (
    DocumentValidationError,
    extract_document,
    validate_document_upload,
)


def make_upload(name, content, content_type):
    return SimpleUploadedFile(name, content, content_type=content_type)


def test_validate_document_rejects_docx_named_pdf():
    """Changing a PDF filename to .docx must not bypass type validation."""
    upload = make_upload('fake.docx', b'%PDF-1.7', 'application/pdf')

    with pytest.raises(DocumentValidationError, match='文件内容与扩展名不一致'):
        validate_document_upload(upload)


def test_validate_document_rejects_legacy_doc_extension():
    """Legacy Word binaries are outside the deliberately small import surface."""
    upload = make_upload('legacy.doc', b'\xd0\xcf\x11\xe0', 'application/msword')

    with pytest.raises(DocumentValidationError, match='仅支持 PDF 和 DOCX'):
        validate_document_upload(upload)


def test_validate_document_rejects_file_larger_than_100_mb():
    """The declared upload size is checked before expensive document parsing."""
    upload = make_upload('large.pdf', b'%PDF-1.7', 'application/pdf')
    upload.size = 100 * 1024 * 1024 + 1

    with pytest.raises(DocumentValidationError, match='100MB'):
        validate_document_upload(upload)


def test_validate_document_rejects_pdf_over_page_limit(tmp_path):
    """An over-limit PDF is rejected at upload validation, before it is queued."""
    pdf_path = tmp_path / 'too-many-pages.pdf'
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    for _ in range(101):
        pdf.drawString(72, 720, '1. A numbered question')
        pdf.showPage()
    pdf.save()

    with pytest.raises(DocumentValidationError, match='100 页'):
        validate_document_upload(make_upload('too-many-pages.pdf', pdf_path.read_bytes(), 'application/pdf'))


def test_validate_document_rejects_docx_over_equivalent_page_limit(tmp_path):
    """The DOCX complexity formula is also enforced before queueing work."""
    document_path = tmp_path / 'too-large.docx'
    document = Document()
    document.add_paragraph('1. ' + '题' * 160_000)
    document.save(document_path)

    with pytest.raises(DocumentValidationError, match='100 页'):
        validate_document_upload(make_upload(
            'too-large.docx', document_path.read_bytes(),
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ))


@pytest.fixture
def pdf_fixture(tmp_path):
    image_path = tmp_path / 'diagram.png'
    image = Image.new('RGB', (10, 10), color='black')
    image.save(image_path)

    pdf_path = tmp_path / 'questions.pdf'
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.drawString(72, 720, '1. First question has an illustration.')
    pdf.drawImage(str(image_path), 72, 650, width=20, height=20)
    pdf.drawString(72, 580, '2. Second question has no illustration.')
    pdf.save()
    pdf_path.write_bytes(buffer.getvalue())
    return pdf_path


def test_extract_pdf_slices_questions_and_binds_assets(pdf_fixture):
    """A numbered PDF is split into independently processable question fragments."""
    document = extract_document(pdf_fixture)

    assert [item.question_no for item in document.fragments] == ['1', '2']
    assert document.fragments[0].asset_refs
    assert document.fragments[0].page_range == (1, 1)


def test_extract_pdf_rejects_more_than_100_pages(tmp_path):
    """Page limits are enforced before a large PDF can enter AI processing."""
    pdf_path = tmp_path / 'too-many-pages.pdf'
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    for _ in range(101):
        pdf.drawString(72, 720, '1. A numbered question')
        pdf.showPage()
    pdf.save()

    with pytest.raises(DocumentValidationError, match='100 页'):
        extract_document(pdf_path)


def test_extract_document_rejects_without_numbered_candidates(tmp_path):
    """Unstructured documents stop before any downstream AI request is possible."""
    pdf_path = tmp_path / 'no-questions.pdf'
    pdf = canvas.Canvas(str(pdf_path), pagesize=letter)
    pdf.drawString(72, 720, 'This page has no numbered question candidates.')
    pdf.save()

    with pytest.raises(DocumentValidationError, match='未找到可识别的编号题目'):
        extract_document(pdf_path)


def test_extract_docx_rejects_equivalent_page_count_above_limit(tmp_path):
    """DOCX complexity is limited by the specified text/table/image page estimate."""
    document_path = tmp_path / 'too-large.docx'
    document = Document()
    document.add_paragraph('1. ' + '题' * 160_000)
    document.save(document_path)

    with pytest.raises(DocumentValidationError, match='100 页'):
        extract_document(document_path)


def test_extract_docx_slices_questions_and_attaches_tables_and_images(tmp_path):
    """DOCX paragraphs, nearby tables, and relationship images stay with their question."""
    image_path = tmp_path / 'diagram.png'
    Image.new('RGB', (10, 10), color='black').save(image_path)
    document_path = tmp_path / 'questions.docx'
    document = Document()
    document.add_paragraph('1. First DOCX question')
    document.add_picture(str(image_path))
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = 'Given value'
    document.add_paragraph('2. Second DOCX question')
    document.save(document_path)

    extracted = extract_document(document_path)

    assert [fragment.question_no for fragment in extracted.fragments] == ['1', '2']
    assert extracted.fragments[0].tables == [[['Given value']]]
    assert extracted.fragments[0].asset_refs
