"""Image cropping helpers shared by parser-backed review workflows."""
import logging
import os

from PIL import Image


logger = logging.getLogger(__name__)


def crop_question_image(page_image_path: str, bbox: dict | list, output_path: str) -> str | None:
    """Crop a region from a page image and save it.

    Args:
        page_image_path: Absolute path to the full page image.
        bbox: Either a dict with keys x1, y1, x2, y2, or a list [x1, y1, x2, y2].
        output_path: Absolute path to save the cropped image.

    Returns:
        Relative path of the cropped image, or None if cropping failed.
    """
    try:
        if isinstance(bbox, list) and len(bbox) == 4:
            x1, y1, x2, y2 = bbox
        else:
            x1 = bbox.get('x1', 0)
            y1 = bbox.get('y1', 0)
            x2 = bbox.get('x2', 0)
            y2 = bbox.get('y2', 0)
        with Image.open(page_image_path) as img:
            cropped = img.crop((x1, y1, x2, y2))
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            cropped.save(output_path)
            return output_path
    except Exception as e:
        logger.warning(f'Failed to crop image: {e}')
        return None
