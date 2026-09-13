"""Safe, deterministic extraction primitives for course PDF and DOCX imports."""

from dataclasses import dataclass, field
from io import BytesIO
from math import ceil
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

import fitz
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


MAX_DOCUMENT_BYTES = 100 * 1024 * 1024
MAX_DOCUMENT_PAGES = 100
QUESTION_START = re.compile(r'(?m)^\s*(\d+)\s*[.、．)]\s*')
RELATION_IMAGE_SUFFIX = '/image'


class DocumentValidationError(ValueError):
    """Raised before an invalid document can reach an AI processing stage."""


@dataclass(frozen=True)
class ValidatedDocument:
    filename: str
    document_type: str
    detected_mime: str
    size_bytes: int
    page_count: int


@dataclass(frozen=True)
class DocumentAssetRef:
    reference: str
    page_no: int | None = None
    bbox: tuple[float, float, float, float] | None = None


@dataclass
class ExtractedQuestionFragment:
    question_no: str
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)
    page_range: tuple[int, int] = (1, 1)
    asset_refs: list[DocumentAssetRef] = field(default_factory=list)


@dataclass
class ExtractedDocument:
    document_type: str
    page_count: int
    fragments: list[ExtractedQuestionFragment]


def validate_document_upload(uploaded_file) -> ValidatedDocument:
    """Validate a Django upload using both its extension and its actual bytes."""
    filename = str(getattr(uploaded_file, 'name', ''))
    extension = Path(filename).suffix.lower()
    if extension not in {'.pdf', '.docx'}:
        raise DocumentValidationError('仅支持 PDF 和 DOCX 格式文件')

    size_bytes = int(getattr(uploaded_file, 'size', 0))
    if size_bytes > MAX_DOCUMENT_BYTES:
        raise DocumentValidationError('文件大小不能超过 100MB')

    content = _read_upload_bytes(uploaded_file)
    document_type = _detect_document_type(content)
    if document_type is None:
        raise DocumentValidationError('文件内容无法识别为 PDF 或 DOCX')
    if document_type != extension.lstrip('.'):
        raise DocumentValidationError('文件内容与扩展名不一致')
    page_count = _validate_document_page_limit(document_type, content)
    return ValidatedDocument(
        filename=filename,
        document_type=document_type,
        detected_mime='application/pdf' if document_type == 'pdf'
        else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        size_bytes=size_bytes,
        page_count=page_count,
    )


def extract_document(source_path) -> ExtractedDocument:
    """Extract numbered question candidates and nearby image references from a document."""
    path = Path(source_path)
    _validate_source_path(path)
    document_type = path.suffix.lower().lstrip('.')
    if document_type == 'pdf':
        return _extract_pdf(path)
    return _extract_docx(path)


def _read_upload_bytes(uploaded_file) -> bytes:
    try:
        uploaded_file.seek(0)
    except (AttributeError, OSError):
        pass
    content = uploaded_file.read()
    try:
        uploaded_file.seek(0)
    except (AttributeError, OSError):
        pass
    return content


def _detect_document_type(content: bytes) -> str | None:
    if content.startswith(b'%PDF-'):
        return 'pdf'
    try:
        with ZipFile(BytesIO(content)) as archive:
            if 'word/document.xml' in archive.namelist():
                return 'docx'
    except BadZipFile:
        return None
    return None


def _validate_source_path(path: Path) -> None:
    extension = path.suffix.lower()
    if extension not in {'.pdf', '.docx'}:
        raise DocumentValidationError('仅支持 PDF 和 DOCX 格式文件')
    size_bytes = path.stat().st_size
    if size_bytes > MAX_DOCUMENT_BYTES:
        raise DocumentValidationError('文件大小不能超过 100MB')
    document_type = _detect_document_type(path.read_bytes())
    if document_type is None:
        raise DocumentValidationError('文件内容无法识别为 PDF 或 DOCX')
    if document_type != extension.lstrip('.'):
        raise DocumentValidationError('文件内容与扩展名不一致')


def _validate_document_page_limit(document_type: str, content: bytes) -> int:
    if document_type == 'pdf':
        try:
            pdf = fitz.open(stream=content, filetype='pdf')
        except (fitz.FileDataError, RuntimeError) as exc:
            raise DocumentValidationError('无法读取 PDF 文件') from exc
        with pdf:
            page_count = len(pdf)
        if page_count > MAX_DOCUMENT_PAGES:
            raise DocumentValidationError('PDF 文档不能超过 100 页')
        return page_count

    try:
        document = Document(BytesIO(content))
    except Exception as exc:  # python-docx raises several package-specific errors.
        raise DocumentValidationError('无法读取 DOCX 文件') from exc
    page_count = _docx_equivalent_page_count(document)
    if page_count > MAX_DOCUMENT_PAGES:
        raise DocumentValidationError('DOCX 文档等价页数不能超过 100 页')
    return page_count


def _extract_pdf(path: Path) -> ExtractedDocument:
    try:
        pdf = fitz.open(path)
    except (fitz.FileDataError, RuntimeError) as exc:
        raise DocumentValidationError('无法读取 PDF 文件') from exc
    with pdf:
        page_count = len(pdf)
        if page_count > MAX_DOCUMENT_PAGES:
            raise DocumentValidationError('PDF 文档不能超过 100 页')
        page_details = [_pdf_page_detail(page, number + 1) for number, page in enumerate(pdf)]

    fragments = _pdf_fragments(page_details)
    if not fragments:
        raise DocumentValidationError('未找到可识别的编号题目')
    return ExtractedDocument(document_type='pdf', page_count=page_count, fragments=fragments)


def _pdf_page_detail(page, page_no: int) -> dict:
    blocks = sorted(page.get_text('blocks'), key=lambda block: (block[1], block[0]))
    text = '\n'.join(block[4] for block in blocks)
    starts = []
    for match in QUESTION_START.finditer(text):
        prefix = match.group(0).strip()
        rectangles = page.search_for(prefix)
        starts.append({
            'question_no': match.group(1),
            'offset': match.start(),
            'y': rectangles[0].y0 if rectangles else 0,
        })
    assets = []
    for image in page.get_images(full=True):
        xref = image[0]
        for rectangle in page.get_image_rects(xref):
            assets.append(DocumentAssetRef(
                reference=f'pdf:{xref}', page_no=page_no,
                bbox=(rectangle.x0, rectangle.y0, rectangle.x1, rectangle.y1),
            ))
    return {'page_no': page_no, 'text': text, 'blocks': blocks, 'starts': starts, 'assets': assets}


def _pdf_fragments(page_details: list[dict]) -> list[ExtractedQuestionFragment]:
    candidates = [
        {**start, 'page_index': index, 'page_no': detail['page_no']}
        for index, detail in enumerate(page_details)
        for start in detail['starts']
    ]
    fragments = []
    for index, candidate in enumerate(candidates):
        following = candidates[index + 1] if index + 1 < len(candidates) else None
        end_index = following['page_index'] if following else len(page_details) - 1
        text_parts = []
        for page_index in range(candidate['page_index'], end_index + 1):
            page_text = page_details[page_index]['text']
            start_offset = candidate['offset'] if page_index == candidate['page_index'] else 0
            end_offset = following['offset'] if following and page_index == end_index else len(page_text)
            text_parts.append(page_text[start_offset:end_offset].strip())
        fragments.append(ExtractedQuestionFragment(
            question_no=candidate['question_no'],
            text='\n'.join(part for part in text_parts if part),
            page_range=(candidate['page_no'], page_details[end_index]['page_no']),
            asset_refs=_pdf_assets_for_candidate(candidate, following, page_details),
        ))
    return fragments


def _pdf_assets_for_candidate(candidate: dict, following: dict | None, page_details: list[dict]):
    assets = []
    end_index = following['page_index'] if following else len(page_details) - 1
    for page_index in range(candidate['page_index'], end_index + 1):
        for asset in page_details[page_index]['assets']:
            y_center = (asset.bbox[1] + asset.bbox[3]) / 2 if asset.bbox else 0
            if page_index == candidate['page_index'] and y_center < candidate['y']:
                continue
            if following and page_index == following['page_index'] and y_center >= following['y']:
                continue
            assets.append(asset)
    return assets


def _extract_docx(path: Path) -> ExtractedDocument:
    try:
        document = Document(str(path))
    except Exception as exc:  # python-docx raises several package-specific errors.
        raise DocumentValidationError('无法读取 DOCX 文件') from exc

    image_refs = _docx_image_references(document)
    page_count = _docx_equivalent_page_count(document, image_refs)
    if page_count > MAX_DOCUMENT_PAGES:
        raise DocumentValidationError('DOCX 文档等价页数不能超过 100 页')

    fragments = _docx_fragments(document, image_refs, max(page_count, 1))
    if not fragments:
        raise DocumentValidationError('未找到可识别的编号题目')
    return ExtractedDocument(document_type='docx', page_count=page_count, fragments=fragments)


def _docx_non_whitespace_characters(document) -> int:
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return len(re.sub(r'\s+', '', ''.join(parts)))


def _docx_equivalent_page_count(document, image_refs: dict[str, DocumentAssetRef] | None = None) -> int:
    image_refs = image_refs if image_refs is not None else _docx_image_references(document)
    return (
        ceil(_docx_non_whitespace_characters(document) / 1600)
        + ceil(len(document.tables) / 2)
        + len(image_refs)
    )


def _docx_image_references(document) -> dict[str, DocumentAssetRef]:
    return {
        relation_id: DocumentAssetRef(reference=f'docx:{relation.target_part.partname}')
        for relation_id, relation in document.part.rels.items()
        if relation.reltype.endswith(RELATION_IMAGE_SUFFIX)
    }


def _docx_fragments(document, image_refs: dict[str, DocumentAssetRef], page_count: int):
    fragments = []
    current = None
    pending_assets = []
    for item in _docx_body_items(document):
        if isinstance(item, Paragraph):
            match = QUESTION_START.match(item.text)
            paragraph_assets = _paragraph_asset_refs(item, image_refs)
            if match:
                current = ExtractedQuestionFragment(
                    question_no=match.group(1), text=item.text[match.start():].strip(),
                    page_range=(1, page_count), asset_refs=pending_assets + paragraph_assets,
                )
                fragments.append(current)
                pending_assets = []
            elif current is None:
                pending_assets.extend(paragraph_assets)
            else:
                if item.text.strip():
                    current.text = f'{current.text}\n{item.text.strip()}'.strip()
                current.asset_refs.extend(paragraph_assets)
        elif current is not None:
            current.tables.append([[cell.text for cell in row.cells] for row in item.rows])
    return fragments


def _docx_body_items(document):
    for child in document.element.body.iterchildren():
        if child.tag.endswith('}p'):
            yield Paragraph(child, document)
        elif child.tag.endswith('}tbl'):
            yield Table(child, document)


def _paragraph_asset_refs(paragraph, image_refs: dict[str, DocumentAssetRef]):
    relation_ids = re.findall(r'r:embed="([^"]+)"', paragraph._element.xml)
    return [image_refs[relation_id] for relation_id in relation_ids if relation_id in image_refs]
