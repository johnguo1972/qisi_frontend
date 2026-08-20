from __future__ import annotations

import pytest

from apps.common.exceptions import AIRequestError
from apps.common.ai import provider_limiter


def test_provider_limits_fall_back_to_the_six_request_safety_cap(monkeypatch):
    """Missing settings must never silently restore the former 16-way limit."""
    monkeypatch.delattr(
        provider_limiter.settings, "AI_QWEN_CONCURRENCY", raising=False
    )
    monkeypatch.delattr(
        provider_limiter.settings, "AI_DEEPSEEK_CONCURRENCY", raising=False
    )

    assert provider_limiter._limit_for("qwen") == 6
    assert provider_limiter._limit_for("deepseek") == 6


def test_provider_lease_waits_for_a_redis_slot_before_failing(monkeypatch):
    """A brief saturation must wait rather than turn a valid B call into failure."""
    events = []

    class FakePool:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self, owner):
            events.append(("acquire", owner))
            return len([event for event in events if event[0] == "acquire"]) > 1

        def release(self, owner):
            events.append(("release", owner))
            return True

    ticks = iter((0.0, 0.0, 0.2))
    with monkeypatch.context() as patch:
        patch.setattr(provider_limiter, "RedisLeasePool", FakePool)
        patch.setattr(provider_limiter.time, "monotonic", lambda: next(ticks))
        patch.setattr(provider_limiter.time, "sleep", lambda seconds: events.append(("sleep", seconds)))
        patch.setattr(provider_limiter.settings, "AI_PROVIDER_LEASE_WAIT_SECONDS", 5, raising=False)
        patch.setattr(provider_limiter.settings, "AI_PROVIDER_LEASE_POLL_SECONDS", 1, raising=False)

        with provider_limiter.provider_request_lease("deepseek"):
            events.append(("work",))

    assert [event[0] for event in events] == ["acquire", "sleep", "acquire", "work", "release"]


def test_provider_lease_still_fails_after_wait_budget_is_exhausted(monkeypatch):
    class FakePool:
        def __init__(self, *_args, **_kwargs):
            pass

        def acquire(self, _owner):
            return False

        def release(self, _owner):
            raise AssertionError("an unacquired lease must not be released")

    ticks = iter((0.0, 0.0, 5.0))
    with monkeypatch.context() as patch:
        patch.setattr(provider_limiter, "RedisLeasePool", FakePool)
        patch.setattr(provider_limiter.time, "monotonic", lambda: next(ticks))
        patch.setattr(provider_limiter.time, "sleep", lambda _seconds: None)
        patch.setattr(provider_limiter.settings, "AI_PROVIDER_LEASE_WAIT_SECONDS", 5, raising=False)
        patch.setattr(provider_limiter.settings, "AI_PROVIDER_LEASE_POLL_SECONDS", 1, raising=False)

        with pytest.raises(AIRequestError, match="capacity unavailable"):
            with provider_limiter.provider_request_lease("deepseek"):
                pass
