"""Runtime feature gates for the practice beta rollout.

The gate is intentionally environment based so disabling the feature only
requires changing deployment configuration and restarting the API process.
"""
from __future__ import annotations

from django.conf import settings


def practice_beta_mobiles() -> frozenset[str]:
    configured = getattr(settings, 'PRACTICE_BETA_MOBILES', ())
    if isinstance(configured, str):
        configured = configured.split(',')
    return frozenset(str(value).strip() for value in configured if str(value).strip())


def practice_feature_enabled_for(user) -> bool:
    if not bool(getattr(settings, 'PRACTICE_FEATURE_ENABLED', False)):
        return False
    allowlist = practice_beta_mobiles()
    if not allowlist:
        return True
    return str(getattr(user, 'mobile', '') or '').strip() in allowlist


def practice_feature_state() -> dict:
    allowlist = practice_beta_mobiles()
    return {
        'enabled': bool(getattr(settings, 'PRACTICE_FEATURE_ENABLED', False)),
        'beta_allowlist_configured': bool(allowlist),
        'beta_account_count': len(allowlist),
        'release_version': str(getattr(settings, 'PRACTICE_RELEASE_VERSION', 'phase5')),
    }
