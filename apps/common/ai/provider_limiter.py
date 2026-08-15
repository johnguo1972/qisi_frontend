"""Short-lived provider request leases for Qwen and DeepSeek HTTP calls."""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager

from django.conf import settings

from apps.common.exceptions import AIRequestError
from apps.review.ai_queue import RedisLeasePool


def _limit_for(provider: str) -> int:
    if provider == 'deepseek':
        return int(getattr(settings, 'AI_DEEPSEEK_CONCURRENCY', 8))
    return int(getattr(settings, 'AI_QWEN_CONCURRENCY', 16))


@contextmanager
def provider_request_lease(provider: str):
    """Lease one provider slot exactly for the duration of an HTTP request."""
    owner = f'{provider}:{uuid.uuid4()}'
    pool = RedisLeasePool(
        f'provider:{provider}', limit=_limit_for(provider), ttl_seconds=4200,
    )
    try:
        acquired = pool.acquire(owner)
    except Exception as error:
        raise AIRequestError('AI provider capacity unavailable') from error
    if not acquired:
        raise AIRequestError('AI provider capacity unavailable')
    try:
        yield
    finally:
        try:
            pool.release(owner)
        except Exception:
            # The bounded lease will expire.  Never mask the provider result.
            pass
