"""Custom exceptions for the exam parser system."""


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
