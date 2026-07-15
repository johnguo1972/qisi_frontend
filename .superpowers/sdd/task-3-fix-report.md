# Task 3 Fix Report

**Status:** DONE

**Commit:** 4ae708a - `fix(courses): C1+C2+I2+I4 variant task critical fixes`

**Tests:** 30/30 passing (22 existing + 8 new units tests)

**Django check:** System check identified no issues.

## Changes Summary

| Fix | File | Change |
|-----|------|--------|
| C1 | `apps/courses/validator.py` | Added `VALID_UNITS` set (30+ units) and `_check_units()` method |
| C1 | `apps/courses/tests/test_validator.py` | Added `TestVariantValidatorUnits` class with 8 test cases |
| C2 | `apps/courses/ai_service.py` | Created `VariantAIService` class, replaced `ValueError` with `AIRequestError`, added backward-compat wrappers |
| I2 | `apps/courses/tasks.py` | `_get_ai_model()` now uses `getattr(settings, ...)` instead of `os.environ.get()` |
| I4 | `apps/courses/tasks.py` | Validator failures are hard (no Celery retry), DeepSeek verifier gets independent retry_budget=1 |
