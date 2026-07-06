"""Template filters for common utilities."""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def path_to_url(value):
    """Convert Windows backslash paths to forward-slash URL paths."""
    if not value:
        return value
    return str(value).replace('\\', '/')


@register.filter(needs_autoescape=True)
def wrap_math(value, autoescape=True):
    """Wrap LaTeX content in $...$ delimiters if not already present."""
    if not value:
        return value
    value = str(value)
    # Don't wrap if already has $ or $$ delimiters
    if '$' in value:
        return value
    # Wrap in inline math delimiters
    return mark_safe(f'${value}$')
