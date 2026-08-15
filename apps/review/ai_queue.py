"""Redis leases and fair, durable dispatch for AI queue items."""

from __future__ import annotations

import time

from django.core.cache import cache


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
