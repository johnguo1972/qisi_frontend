"""Helpers for exposing media files to API clients."""

from django.conf import settings


def media_url(file_path) -> str:
    """Convert a stored media-relative path into a stable client URL."""
    path = str(file_path or '').replace('\\', '/')
    if path.startswith(('http://', 'https://', 'data:')):
        return path
    relative = path.lstrip('/')
    if relative.lower().startswith('media/'):
        relative = relative[6:]
    return f'{settings.MEDIA_URL.rstrip("/")}/{relative}'
