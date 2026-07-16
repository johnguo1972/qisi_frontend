"""Word document to PDF conversion service using LibreOffice."""
import os
import logging
import subprocess
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# LibreOffice executable path
LIBREOFFICE_PATHS = [
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    '/usr/bin/libreoffice',
    '/usr/bin/soffice',
    '/usr/local/bin/libreoffice',
    '/usr/local/bin/soffice',
]


def _find_libreoffice() -> str | None:
    """Find LibreOffice executable path."""
    for path in LIBREOFFICE_PATHS:
        if os.path.exists(path):
            return path
    return None


def convert_word_to_pdf(word_path: str) -> str | None:
    """Convert a Word document (.doc/.docx) to PDF.

    Returns the path to the converted PDF file, or None if conversion failed.
    The PDF is saved alongside the original Word file with the same name but .pdf extension.
    """
    libreoffice = _find_libreoffice()
    if not libreoffice:
        logger.error('LibreOffice not found')
        return None

    word_path = Path(word_path)
    if not word_path.exists():
        logger.error(f'Word file not found: {word_path}')
        return None

    # Determine output PDF path (same directory, same name, .pdf extension)
    pdf_path = word_path.with_suffix('.pdf')

    # If PDF already exists and is newer than the Word file, return cached version
    if pdf_path.exists() and pdf_path.stat().st_mtime >= word_path.stat().st_mtime:
        logger.info(f'Using cached PDF: {pdf_path}')
        return str(pdf_path)

    # Convert using LibreOffice
    try:
        logger.info(f'Converting {word_path} to PDF...')
        result = subprocess.run(
            [
                str(libreoffice),
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(word_path.parent),
                str(word_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,  # 60 seconds max
        )
        if result.returncode != 0:
            logger.error(f'LibreOffice conversion failed: {result.stderr}')
            return None

        if pdf_path.exists():
            logger.info(f'Conversion successful: {pdf_path}')
            return str(pdf_path)
        else:
            logger.error(f'PDF not created after conversion: {pdf_path}')
            return None

    except subprocess.TimeoutExpired:
        logger.error('LibreOffice conversion timed out')
        return None
    except Exception as e:
        logger.error(f'LibreOffice conversion error: {e}')
        return None