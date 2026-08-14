"""Idempotent dispatch for manual single-mode AI review tasks."""

from dataclasses import dataclass
import json
from typing import Literal
import uuid

from django.core.cache import cache


LOCK_TTL_SECONDS = 4200
LOCK_KEY_PREFIX = 'ai-mode-lock:'
COMPARE_AND_DELETE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
""".strip()


@dataclass(frozen=True)
class ModeTaskDispatch:
    task_id: str
    status: Literal['pending', 'running']
    created: bool


def _normalize_mode(mode: str) -> str:
    normalized = mode.strip().upper() if isinstance(mode, str) else ''
    if normalized not in ('A', 'B', 'C'):
        raise ValueError('mode must be A, B, or C')
    return normalized


def _lock_key(question_id: str, mode: str) -> str:
    return f'{LOCK_KEY_PREFIX}{question_id}:{_normalize_mode(mode)}'


def _owner_task_id(value) -> str | None:
    try:
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        owner = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(owner, dict):
        return None
    task_id = owner.get('task_id')
    return task_id if isinstance(task_id, str) and task_id else None


def _stable_unknown_owner_id(key: str, value) -> str:
    """Return a stable opaque ID without mutating malformed/newer lock data."""
    if isinstance(value, bytes):
        fingerprint = value.hex()
    else:
        fingerprint = repr(value)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'{key}:{fingerprint}'))


def release_single_mode_ai_task_lock(
    question_id: str, mode: str, task_id: str | None
) -> bool:
    """Atomically delete a Redis mode lock only for its exact serialized owner."""
    if not task_id:
        return False
    key = _lock_key(str(question_id), mode)
    owner_value = json.dumps(
        {'task_id': str(task_id)}, separators=(',', ':')
    )
    try:
        redis_key = cache.make_and_validate_key(key)
        cache_client = cache._cache
        redis_client = cache_client.get_client(redis_key, write=True)
        serialized_owner = cache_client._serializer.dumps(owner_value)
        deleted = redis_client.eval(
            COMPARE_AND_DELETE_LUA,
            1,
            redis_key,
            serialized_owner,
        )
    except Exception:
        # Ownership cannot be proven atomically on this backend. Fail closed:
        # TTL expiry is safer than deleting a lock that may have a new owner.
        return False
    return bool(deleted)


def dispatch_single_mode_ai_task(
    question_id: str, mode: str, model: str | None
) -> ModeTaskDispatch:
    """Acquire the per-question/mode lock and enqueue exactly one Celery job."""
    from .tasks import single_mode_ai_process_question

    normalized_mode = _normalize_mode(mode)
    normalized_question_id = str(question_id)
    task_id = str(uuid.uuid4())
    key = _lock_key(normalized_question_id, normalized_mode)
    owner_value = json.dumps({'task_id': task_id}, separators=(',', ':'))

    if not cache.add(key, owner_value, timeout=LOCK_TTL_SECONDS):
        existing_value = cache.get(key)
        existing_task_id = _owner_task_id(existing_value)
        return ModeTaskDispatch(
            task_id=existing_task_id
            or _stable_unknown_owner_id(key, existing_value),
            status='running',
            created=False,
        )

    try:
        single_mode_ai_process_question.apply_async(
            args=(normalized_question_id, normalized_mode),
            kwargs={'model': model},
            task_id=task_id,
        )
    except Exception:
        release_single_mode_ai_task_lock(
            normalized_question_id, normalized_mode, task_id
        )
        raise

    return ModeTaskDispatch(task_id=task_id, status='pending', created=True)
