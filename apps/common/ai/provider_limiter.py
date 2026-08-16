"""Short-lived provider request leases for Qwen and DeepSeek HTTP calls."""

from __future__ import annotations

import time
import uuid
import threading
from contextlib import contextmanager

from django.conf import settings

from apps.common.exceptions import AIRequestError
from apps.review.ai_queue import RedisLeasePool

_fallback_lock = threading.Lock()
_fallback_pools: dict[tuple[str, int], threading.BoundedSemaphore] = {}


def _fallback_pool(provider: str, limit: int) -> threading.BoundedSemaphore:
    with _fallback_lock:
        return _fallback_pools.setdefault((provider, limit), threading.BoundedSemaphore(limit))


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
    fallback = None
    try:
        acquired = pool.acquire(owner)
    except Exception:
        # Preserve a bounded limit during transient Redis outages.  Distributed
        # enforcement resumes automatically as soon as Redis is reachable.
        fallback = _fallback_pool(provider, _limit_for(provider))
        acquired = fallback.acquire(blocking=False)
    if not acquired:
        raise AIRequestError('AI provider capacity unavailable')
    try:
        yield
    finally:
        if fallback is not None:
            fallback.release()
        else:
            try:
                pool.release(owner)
            except Exception:
                # The bounded lease will expire. Never mask the provider result.
                pass
