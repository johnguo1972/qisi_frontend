"""Safe image preparation for OpenAI-compatible vision requests."""

from __future__ import annotations

import base64
import binascii
import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError

from apps.common.exceptions import AIRequestError


MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
DEFAULT_MAX_EDGE = 1600
SUPPORTED_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
DATA_IMAGE_MIME_FORMATS = {
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
}
DATA_IMAGE_PATTERN = re.compile(
    r"\Adata:image/(?P<subtype>png|jpeg|webp);base64,"
    r"(?P<payload>[A-Za-z0-9+/]+={0,2})\Z",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _ImageOutcome:
    value: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class _ImagesOutcome:
    value: tuple[str, ...] | None = None
    error: str | None = None


def encode_image_source(source: str, *, max_edge: int = DEFAULT_MAX_EDGE) -> str:
    """Return a validated HTTP(S) URL or compressed JPEG data URI."""
    outcome = _prepare_image_source(source, max_edge=max_edge)
    source = ""
    if outcome.error is not None:
        raise AIRequestError(outcome.error)
    if outcome.value is None:
        raise AIRequestError("Image input is invalid")
    return outcome.value


def prepare_image_sources(
    sources, *, max_edge: int = DEFAULT_MAX_EDGE
) -> tuple[str, ...]:
    """Prepare image sources without changing their relative order."""
    outcome = _prepare_image_sources(sources, max_edge=max_edge)
    sources = ()
    if outcome.error is not None:
        raise AIRequestError(outcome.error)
    if outcome.value is None:
        raise AIRequestError("Image inputs are invalid")
    return outcome.value


def _prepare_image_sources(sources, *, max_edge: int) -> _ImagesOutcome:
    source_items: tuple[object, ...] = ()
    prepared: list[str] = []
    try:
        if isinstance(sources, (str, bytes)):
            return _ImagesOutcome(error="Image inputs must be a sequence")
        source_items = tuple(sources)
        if not source_items:
            return _ImagesOutcome(error="At least one image is required")
        for source in source_items:
            item = _prepare_image_source(source, max_edge=max_edge)
            if item.error is not None or item.value is None:
                return _ImagesOutcome(
                    error=item.error or "Image input is invalid"
                )
            prepared.append(item.value)
        return _ImagesOutcome(value=tuple(prepared))
    except Exception:
        return _ImagesOutcome(error="Image inputs must be a sequence")
    finally:
        sources = ()
        source_items = ()
        prepared.clear()


def _prepare_image_source(source: object, *, max_edge: int) -> _ImageOutcome:
    try:
        if not isinstance(source, str) or not source.strip():
            return _ImageOutcome(error="Image input is invalid")
        if not isinstance(max_edge, int) or max_edge <= 0:
            return _ImageOutcome(error="Image processing limit is invalid")

        candidate = source.strip()
        if candidate.lower().startswith("data:"):
            return _encode_data_image(candidate, max_edge=max_edge)
        parsed = urlsplit(candidate)
        if parsed.scheme.lower() in {"http", "https"}:
            if not parsed.netloc:
                return _ImageOutcome(error="Image URL is invalid")
            return _ImageOutcome(value=candidate)
        is_windows_absolute_path = bool(
            re.match(r"^[A-Za-z]:[\\/]", candidate)
        )
        if parsed.scheme and not is_windows_absolute_path:
            return _ImageOutcome(error="Image URL scheme is unsupported")
        return _encode_local_image(candidate, max_edge=max_edge)
    except Exception:
        return _ImageOutcome(error="Image input is invalid")
    finally:
        source = ""


def _encode_data_image(source: str, *, max_edge: int) -> _ImageOutcome:
    image = None
    input_buffer = None
    output = None
    decoded = b""
    encoded = ""
    try:
        match = DATA_IMAGE_PATTERN.fullmatch(source)
        if match is None:
            return _ImageOutcome(error="Image data URI is invalid or unsupported")
        payload = match.group("payload")
        max_encoded_size = ((MAX_IMAGE_BYTES + 2) // 3) * 4
        if len(payload) > max_encoded_size:
            return _ImageOutcome(error="Image data is too large")
        try:
            decoded = base64.b64decode(payload, validate=True)
        except (ValueError, binascii.Error):
            return _ImageOutcome(error="Image data URI is invalid or unsupported")
        if not decoded:
            return _ImageOutcome(error="Image data is empty")
        if len(decoded) > MAX_IMAGE_BYTES:
            return _ImageOutcome(error="Image data is too large")

        input_buffer = BytesIO(decoded)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(input_buffer)
            expected_format = DATA_IMAGE_MIME_FORMATS[
                match.group("subtype").lower()
            ]
            if image.format != expected_format:
                return _ImageOutcome(error="Image data format does not match MIME type")
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                return _ImageOutcome(error="Image dimensions are unsupported")
            image.load()

        if image.mode != "RGB":
            converted = image.convert("RGB")
            image.close()
            image = converted
        if max(image.size) > max_edge:
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

        output = BytesIO()
        image.save(output, format="JPEG", quality=85, optimize=True)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return _ImageOutcome(value=f"data:image/jpeg;base64,{encoded}")
    except (
        OSError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return _ImageOutcome(error="Image data is invalid or unsupported")
    except Exception:
        return _ImageOutcome(error="Image processing failed")
    finally:
        if image is not None:
            image.close()
        if input_buffer is not None:
            input_buffer.close()
        if output is not None:
            output.close()
        source = ""
        decoded = b""
        encoded = ""


def _encode_local_image(source: str, *, max_edge: int) -> _ImageOutcome:
    image = None
    output = None
    encoded = ""
    try:
        path = Path(source)
        if not path.is_file():
            return _ImageOutcome(error="Image file is unavailable")
        size_bytes = path.stat().st_size
        if size_bytes <= 0:
            return _ImageOutcome(error="Image file is empty")
        if size_bytes > MAX_IMAGE_BYTES:
            return _ImageOutcome(error="Image file is too large")

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(path)
            if image.format not in SUPPORTED_IMAGE_FORMATS:
                return _ImageOutcome(error="Image format is unsupported")
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                return _ImageOutcome(error="Image dimensions are unsupported")
            image.load()

        if image.mode != "RGB":
            converted = image.convert("RGB")
            image.close()
            image = converted
        if max(image.size) > max_edge:
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

        output = BytesIO()
        image.save(output, format="JPEG", quality=85, optimize=True)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return _ImageOutcome(value=f"data:image/jpeg;base64,{encoded}")
    except (
        OSError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return _ImageOutcome(error="Image file is invalid or unsupported")
    except Exception:
        return _ImageOutcome(error="Image processing failed")
    finally:
        if image is not None:
            image.close()
        if output is not None:
            output.close()
        source = ""
        encoded = ""
