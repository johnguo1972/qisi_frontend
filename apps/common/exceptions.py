"""Custom exceptions for the exam parser system."""

import uuid

from rest_framework.views import exception_handler as drf_exception_handler

from .ai.exceptions import AIConfigError, AIPromptError, AIResponseError

__all__ = [
    "AIConfigError",
    "AIPromptError",
    "AIRequestError",
    "AIResponseError",
    "ConversionError",
    "ImageCropError",
    "SchemaValidationError",
    "TaskExecutionError",
    "api_exception_handler",
]


class AIRequestError(Exception):
    """Raised when an AI API request fails."""
    pass


class SchemaValidationError(Exception):
    """Raised when AI output fails schema validation and cannot be repaired."""
    pass


class ConversionError(Exception):
    """Raised when document conversion (Word->PDF->PNG) fails."""
    pass


class TaskExecutionError(Exception):
    """Raised when a Celery task execution fails."""
    pass


class ImageCropError(Exception):
    """Raised when image cropping fails."""
    pass


def api_exception_handler(exc, context):
    """Keep parent read-only failures consistent with the API envelope."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return response

    raw_data = response.data
    detail = raw_data.get('detail') if isinstance(raw_data, dict) else None
    request = context.get('request')
    path = getattr(request, 'path', '') if request else ''
    is_p2_api = (
        path.startswith('/api/v1/handouts/')
        or '/knowledge-matches/' in path
        or '/courses/' in path and ('/classes' in path or '/handouts' in path)
    )
    if is_p2_api:
        if detail is not None:
            message = str(detail)
        elif isinstance(raw_data, list):
            message = '; '.join(str(item) for item in raw_data)
        else:
            message = str(raw_data)
        response.data = {
            'code': response.status_code,
            'message': message,
            'data': None,
            'meta': {},
            'trace_id': uuid.uuid4().hex[:16],
        }
        return response
    if detail == '家长端仅支持查看，不能代替学生答题':
        response.data = {
            'code': 'PARENT_READ_ONLY',
            'message': detail,
            'data': None,
            'trace_id': uuid.uuid4().hex[:16],
        }
    elif detail == '请先选择已绑定的孩子':
        response.data = {
            'code': 'PARENT_CONTEXT_REQUIRED',
            'message': detail,
            'data': None,
            'trace_id': uuid.uuid4().hex[:16],
        }
    return response
