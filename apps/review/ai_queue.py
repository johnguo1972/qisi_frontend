"""Redis leases and fair, durable dispatch for AI queue items."""

from __future__ import annotations

import time
from collections import deque
from datetime import timedelta
from typing import Iterable

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone


_ACQUIRE_LUA = """
local now = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then return 0 end
redis.call('ZADD', KEYS[1], tonumber(ARGV[1]), ARGV[4])
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[5]))
return 1
"""
_RELEASE_LUA = """
if redis.call('ZREM', KEYS[1], ARGV[1]) == 1 then return 1 end
return 0
"""


class RedisLeasePool:
    def __init__(self, name: str, *, limit: int, ttl_seconds: int):
        self.name = name
        self.limit = limit
        self.ttl_seconds = ttl_seconds

    @property
    def key(self) -> str:
        return f'ai-lease:{self.name}'

    def _eval(self, script: str, *args) -> int:
        backend = cache._cache
        key = cache.make_and_validate_key(self.key)
        client = backend.get_client(key, write=True)
        return int(client.eval(script, 1, key, *args))

    def acquire(self, owner: str) -> bool:
        now = int(time.time())
        return bool(self._eval(
            _ACQUIRE_LUA, now + self.ttl_seconds, now, self.limit, owner, self.ttl_seconds
        ))

    def release(self, owner: str) -> bool:
        return bool(self._eval(_RELEASE_LUA, owner))


def select_fair_item_ids(
    job_items: Iterable[tuple[str, Iterable[str]]], *, limit: int
) -> list[str]:
    """Select queued item IDs with four baseline slots then round-robin extras."""
    queues = [(job_id, deque(item_ids)) for job_id, item_ids in job_items]
    selected: list[str] = []
    for _job_id, items in queues:
        for _ in range(min(4, len(items), limit - len(selected))):
            selected.append(items.popleft())
        if len(selected) == limit:
            return selected
    while len(selected) < limit:
        progressed = False
        for _job_id, items in queues:
            if items:
                selected.append(items.popleft())
                progressed = True
                if len(selected) == limit:
                    return selected
        if not progressed:
            break
    return selected


def reserve_queued_item_ids(*, limit: int | None = None) -> list[str]:
    """Atomically reserve a fair set of queued items for later Celery enqueue."""
    from .models import AIProcessingJob, AIProcessingJobItem

    capacity = limit if limit is not None else int(getattr(settings, 'AI_GLOBAL_CONCURRENCY', 16))
    jobs = list(AIProcessingJob.objects.filter(
        status__in=(AIProcessingJob.Status.QUEUED, AIProcessingJob.Status.RUNNING),
        cancel_requested=False,
    ).order_by('created_at')[:3])
    candidates = select_fair_item_ids(
        [
            (str(job.id), job.items.filter(status=AIProcessingJobItem.Status.QUEUED)
             .order_by('created_at').values_list('id', flat=True))
            for job in jobs
        ],
        limit=capacity,
    )
    pool = RedisLeasePool('question', limit=capacity, ttl_seconds=4200)
    reserved: list[str] = []
    with transaction.atomic():
        for item_id in candidates:
            item = AIProcessingJobItem.objects.select_for_update().get(id=item_id)
            if item.status != AIProcessingJobItem.Status.QUEUED or not pool.acquire(str(item.id)):
                continue
            item.status = AIProcessingJobItem.Status.DISPATCHED
            item.save(update_fields=['status'])
            reserved.append(str(item.id))
    return reserved


def dispatch_queued_ai_items(*, limit: int | None = None) -> int:
    """Send reserved durable items to the dedicated Celery AI queue."""
    from .models import AIProcessingJobItem
    from .tasks import execute_ai_job_item

    item_ids = reserve_queued_item_ids(limit=limit)
    dispatched = 0
    for item_id in item_ids:
        try:
            execute_ai_job_item.apply_async(args=(item_id,), queue='ai.batch')
            dispatched += 1
        except Exception:
            AIProcessingJobItem.objects.filter(
                id=item_id, status=AIProcessingJobItem.Status.DISPATCHED,
            ).update(status=AIProcessingJobItem.Status.QUEUED)
            RedisLeasePool(
                'question',
                limit=limit if limit is not None else int(getattr(settings, 'AI_GLOBAL_CONCURRENCY', 16)),
                ttl_seconds=4200,
            ).release(str(item_id))
    return dispatched


def recover_stale_ai_items(*, now=None, timeout_seconds: int = 4200) -> int:
    """Return items abandoned by a lost worker to the durable queue.

    A running item remains authoritative in PostgreSQL.  Only items whose
    running lease is older than its maximum lifetime are reclaimed; completed
    and recently running work is never touched.
    """
    from .models import AIProcessingJobItem

    now = now or timezone.now()
    cutoff = now - timedelta(seconds=timeout_seconds)
    pool = RedisLeasePool(
        'question',
        limit=int(getattr(settings, 'AI_GLOBAL_CONCURRENCY', 16)),
        ttl_seconds=4200,
    )
    recovered: list[str] = []
    with transaction.atomic():
        stale_items = list(
            AIProcessingJobItem.objects.select_for_update(skip_locked=True).filter(
                status=AIProcessingJobItem.Status.RUNNING,
                started_at__lt=cutoff,
            )
        )
        for item in stale_items:
            item.status = AIProcessingJobItem.Status.QUEUED
            item.celery_task_id = None
            item.error_code = 'worker_lost'
            item.started_at = None
            item.save(update_fields=['status', 'celery_task_id', 'error_code', 'started_at'])
            recovered.append(str(item.id))
    for item_id in recovered:
        pool.release(item_id)
    return len(recovered)
