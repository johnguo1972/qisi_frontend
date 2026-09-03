"""Utilities for turning imported formula assets into browser-ready HTML."""

from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
from pathlib import Path


FORMULA_PLACEHOLDER_RE = re.compile(r"\[\[formula:([^\]]+)\]\]")
WEB_IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'}
CONVERTIBLE_METAFILE_SUFFIXES = {'.wmf', '.emf'}


class FormulaAssetConversionError(RuntimeError):
    """Raised when an imported formula image cannot be made browser-readable."""


def formula_key_from_path(file_path: str | Path, question_id: object = None) -> str:
    """Return the placeholder key represented by an imported asset filename."""
    stem = Path(str(file_path or '')).stem
    question_prefix = f'{question_id}_' if question_id else ''
    if question_prefix and stem.startswith(question_prefix):
        stem = stem[len(question_prefix):]
    match = re.search(r'([A-Za-z0-9]+_formula_\d+)$', stem)
    return match.group(1) if match else stem


def formula_key_from_asset(asset_data: dict) -> str:
    """Resolve a formula placeholder key from supported JSON asset fields."""
    for field in ('id', 'formula_id', 'key', 'name'):
        value = str(asset_data.get(field) or '').strip()
        if value:
            return value.removeprefix('formula:')
    return formula_key_from_path(asset_data.get('file', ''))


def convert_formula_asset(source: Path, destination: Path) -> Path:
    """Copy or convert a formula asset to a browser-supported image format."""
    source = Path(source)
    suffix = source.suffix.lower()
    if suffix in WEB_IMAGE_SUFFIXES:
        output = Path(destination).with_suffix(suffix)
        output.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != output.resolve():
            shutil.copy2(source, output)
        return output

    if suffix not in CONVERTIBLE_METAFILE_SUFFIXES:
        raise FormulaAssetConversionError(f'Unsupported formula image format: {suffix or "unknown"}')

    output = Path(destination).with_suffix('.png')
    output.parent.mkdir(parents=True, exist_ok=True)
    magick = shutil.which('magick')
    convert = shutil.which('convert') if os.name != 'nt' else None
    executable = magick or convert
    if not executable:
        raise FormulaAssetConversionError(
            'WMF/EMF formula conversion requires ImageMagick (magick or convert)'
        )

    command = [
        executable,
        '-density', '300',
        str(source),
        '-background', 'white',
        '-alpha', 'remove',
        '-trim',
        '+repage',
        str(output),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        detail = getattr(exc, 'stderr', '') or str(exc)
        raise FormulaAssetConversionError(f'Failed to convert {source.name}: {detail[:300]}') from exc
    if not output.exists() or output.stat().st_size == 0:
        raise FormulaAssetConversionError(f'Formula conversion produced no output: {source.name}')
    return output


def render_formula_placeholders(
    value: object,
    formula_urls: dict[str, str],
) -> tuple[str, list[str]]:
    """Replace ``[[formula:key]]`` tokens with inline browser images."""
    text = str(value or '')
    missing: list[str] = []

    def replace(match: re.Match) -> str:
        key = match.group(1).strip()
        url = formula_urls.get(key)
        if not url:
            if key not in missing:
                missing.append(key)
            return match.group(0)
        safe_key = html.escape(key, quote=True)
        safe_url = html.escape(url, quote=True)
        return (
            '<img class="inline-formula" '
            f'data-formula-key="{safe_key}" src="{safe_url}" alt="公式" '
            'style="display:inline-block;max-width:100%;height:auto;vertical-align:middle;" />'
        )

    return FORMULA_PLACEHOLDER_RE.sub(replace, text), missing
