"""Document conversion service: Word -> PDF -> PNG."""
import os
import sys
import logging
import subprocess
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)


def _find_libreoffice() -> str:
    """Find the LibreOffice executable path.

    On Linux/mac: 'libreoffice' should be in PATH.
    On Windows: check common installation directories and settings.LIBREOFFICE_PATH.

    Returns:
        Path to the 'soffice' or 'libreoffice' executable.

    Raises:
        RuntimeError: If LibreOffice cannot be found.
    """
    # 1. Try settings override
    custom_path = getattr(settings, 'LIBREOFFICE_PATH', None)
    if custom_path and os.path.exists(custom_path):
        return custom_path

    # 2. Try 'libreoffice' in PATH (Linux/mac or Windows if added)
    try:
        result = subprocess.run(
            ['libreoffice', '--version'],
            capture_output=True, timeout=5
        )
        if result.returncode == 0:
            return 'libreoffice'
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 3. Windows common paths
    if sys.platform == 'win32':
        candidates = [
            r'C:\Program Files\LibreOffice\program\soffice.exe',
            r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate

    raise RuntimeError(
        'LibreOffice not found. Install it or set LIBREOFFICE_PATH in Django settings.\n'
        'Linux: sudo apt install libreoffice\n'
        'Windows: https://www.libreoffice.org/download/ (usually C:\\Program Files\\LibreOffice\\program\\soffice.exe)'
    )


def word_to_pdf(word_path: str, output_dir: str = None) -> str:
    """Convert a Word document to PDF using LibreOffice.

    Args:
        word_path: Path to the .docx file.
        output_dir: Directory for the PDF output. Defaults to same dir as word_path.

    Returns:
        Path to the generated PDF file.

    Raises:
        RuntimeError: If LibreOffice is not available or conversion fails.
    """
    if output_dir is None:
        output_dir = os.path.dirname(word_path)

    os.makedirs(output_dir, exist_ok=True)

    libreoffice_bin = _find_libreoffice()
    cmd = [
        libreoffice_bin, '--headless', '--convert-to', 'pdf',
        word_path, '--outdir', output_dir
    ]

    logger.info(f'Converting Word to PDF: {word_path}')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(f'LibreOffice conversion failed: {result.stderr}')

    # PDF has same base name as Word file
    pdf_name = Path(word_path).stem + '.pdf'
    pdf_path = os.path.join(output_dir, pdf_name)

    if not os.path.exists(pdf_path):
        raise RuntimeError(f'PDF file not found after conversion: {pdf_path}')

    logger.info(f'PDF created: {pdf_path}')
    # Return path relative to MEDIA_ROOT
    rel_path = os.path.relpath(pdf_path, settings.MEDIA_ROOT)
    return rel_path


def pdf_to_images(pdf_path: str, output_dir: str = None, dpi: int = 300) -> list:
    """Convert a PDF to a list of PNG images.

    Uses PyMuPDF (fitz) as primary renderer (cross-platform, no system deps).
    Falls back to pdf2image if PyMuPDF is unavailable.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory for image output. Defaults to 'pages/' next to PDF.
        dpi: Resolution for rendering.

    Returns:
        List of dicts with keys: page_no, path (relative to MEDIA_ROOT), width, height.

    Raises:
        RuntimeError: If neither PyMuPDF nor pdf2image/poppler is available.
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(pdf_path), 'pages')

    os.makedirs(output_dir, exist_ok=True)

    # Try PyMuPDF first (cross-platform, no system dependencies)
    try:
        import fitz
        return _pdf_to_images_pymupdf(pdf_path, output_dir, dpi, fitz)
    except ImportError:
        pass

    # Fallback to pdf2image
    try:
        from pdf2image import convert_from_path
        return _pdf_to_images_pdf2image(pdf_path, output_dir, dpi, convert_from_path)
    except ImportError:
        pass

    raise RuntimeError(
        'Neither PyMuPDF nor pdf2image is available.\n'
        'Recommended: pip install PyMuPDF\n'
        'Alternative: pip install pdf2image (requires poppler on Windows)'
    )


def _pdf_to_images_pymupdf(pdf_path: str, output_dir: str, dpi: int, fitz) -> list:
    """Render PDF pages to PNG images using PyMuPDF."""
    logger.info(f'Converting PDF to images at {dpi} DPI: {pdf_path} (PyMuPDF)')
    doc = fitz.open(pdf_path)
    image_paths = []

    # PyMuPDF renders at 72 DPI by default; scale factor for target DPI
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    for i in range(len(doc)):
        page = doc[i]
        pix = page.get_pixmap(matrix=mat)
        image_path = os.path.join(output_dir, f'page_{i+1:03d}.png')
        pix.save(image_path)
        width, height = pix.width, pix.height
        rel_path = os.path.relpath(image_path, settings.MEDIA_ROOT)
        image_paths.append({
            'page_no': i + 1,
            'path': rel_path,
            'width': width,
            'height': height,
        })
        logger.info(f'Saved page image: {image_path} ({width}x{height})')

    doc.close()
    return image_paths


def _pdf_to_images_pdf2image(pdf_path: str, output_dir: str, dpi: int, convert_from_path) -> list:
    """Render PDF pages to PNG images using pdf2image."""
    logger.info(f'Converting PDF to images at {dpi} DPI: {pdf_path} (pdf2image)')
    images = convert_from_path(pdf_path, dpi=dpi)

    image_paths = []
    for i, image in enumerate(images, start=1):
        image_path = os.path.join(output_dir, f'page_{i:03d}.png')
        image.save(image_path, 'PNG')
        width, height = image.size
        rel_path = os.path.relpath(image_path, settings.MEDIA_ROOT)
        image_paths.append({
            'page_no': i,
            'path': rel_path,
            'width': width,
            'height': height,
        })
        logger.info(f'Saved page image: {image_path} ({width}x{height})')

    return image_paths
