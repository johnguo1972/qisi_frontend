"""Small structured logging helpers for the practice rollout."""
import logging


logger = logging.getLogger('apps.practice')


def log_practice_event(event: str, *, level=logging.INFO, **fields):
    safe_fields = {key: value for key, value in fields.items() if value is not None}
    logger.log(level, 'practice_event=%s fields=%s', event, safe_fields)
