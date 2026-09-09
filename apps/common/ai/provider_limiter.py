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
        return int(getattr(settings, 'AI_DEEPSEEK_CONCURRENCY', 6))
    return int(getattr(settings, 'AI_QWEN_CONCURRENCY', 6))


def _lease_wait_seconds(wait_seconds: float | None = None) -> float:
    configured = (
        wait_seconds
        if wait_seconds is not None
        else getattr(settings, 'AI_PROVIDER_LEASE_WAIT_SECONDS', 300)
    )
    return max(0.0, float(configured))


def _lease_poll_seconds() -> float:
    return max(0.1, float(getattr(settings, 'AI_PROVIDER_LEASE_POLL_SECONDS', 2)))


def _acquire_redis_lease(
    pool: RedisLeasePool, owner: str, wait_seconds: float | None = None
) -> bool:
    """Wait briefly for a distributed provider slot without exceeding its cap."""
    deadline = time.monotonic() + _lease_wait_seconds(wait_seconds)
    while True:
        if pool.acquire(owner):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(_lease_poll_seconds(), remaining))


@contextmanager
def provider_request_lease(provider: str, wait_seconds: float | None = None):
    """Lease one provider slot exactly for the duration of an HTTP request."""
    owner = f'{provider}:{uuid.uuid4()}'
    pool = RedisLeasePool(
        f'provider:{provider}', limit=_limit_for(provider), ttl_seconds=4200,
    )
    fallback = None
    try:
        acquired = _acquire_redis_lease(pool, owner, wait_seconds)
    except Exception:
        # Preserve a bounded limit during transient Redis outages.  Distributed
        # enforcement resumes automatically as soon as Redis is reachable.
        fallback = _fallback_pool(provider, _limit_for(provider))
        acquired = fallback.acquire(timeout=_lease_wait_seconds(wait_seconds))
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
