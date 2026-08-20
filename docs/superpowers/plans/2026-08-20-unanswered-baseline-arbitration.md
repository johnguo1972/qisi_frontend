# 无答案题仲裁与六路并发实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让无答案题以持久化 DeepSeek 基线驱动 A/B/C 模式仲裁，并将 AI 并发限制为六路。

**Architecture:** 复用现有 `AIReviewService.solve_unanswered_*` 与 `ModeAnswerArbitrator.process_unanswered`。新增统一的基线确保入口，单模式任务按基线分支选择仲裁方法；错误信息采用脱敏结构化记录。

**Tech Stack:** Django 5、Celery、Redis、Pydantic、pytest。

**Spec:** `docs/superpowers/specs/2026-08-20-unanswered-baseline-arbitration-design.md`

## Global Constraints

- 仅修改 `./front`。
- 不记录模型原文、提示词、密钥或题面隐私内容。
- 每一步完成即保存。
- Celery、题目、Qwen、DeepSeek 的并发上限均为 6。

### Task 1: 无答案基线统一入口

**Files:**
- Modify: `apps/common/ai_service.py`
- Test: `apps/common/ai/tests/test_review_compatibility.py`

- [ ] 为缺少原始答案的题目提供复用或生成并立即持久化的基线入口。
- [ ] 测试已有基线不重复调用 DeepSeek，缺失基线会保存答案与解析，基线失败阻止模式生成。

### Task 2: 单模式 A/B/C 采用正确仲裁分支

**Files:**
- Modify: `apps/review/tasks.py`
- Test: `apps/review/tests.py`, `apps/common/ai/tests/test_review_compatibility.py`

- [ ] 单模式任务识别无答案基线并调用 `solve_unanswered_mode_with_arbitration`。
- [ ] 测试 B 模式只比较最终答案，冲突才调用最终复核，第二次失败记录错误。

### Task 3: B 模式诊断与结构修复

**Files:**
- Modify: `apps/common/ai/components/mode_answers.py`, `apps/common/ai_service.py`, `apps/review/tasks.py`
- Test: `apps/common/ai/tests/test_question_components.py`, `apps/review/tests.py`

- [ ] 将 Schema 校验问题转换为脱敏字段路径。
- [ ] 为首次 B 模式结构失败增加一次仅结构修复的 Qwen 调用。
- [ ] 测试结构修复成功、再次失败及不泄露原始响应。

### Task 4: 六路并发配置

**Files:**
- Modify: `config/settings.py`, `.env.example`（若存在）
- Test: `apps/review/tests.py`

- [ ] 默认全局、Qwen、DeepSeek 并发均为 6。
- [ ] 部署说明指定 Celery `--concurrency=6` 与生产 `.env` 的四个并发变量。

### Task 5: 回归与恢复批次

**Files:**
- Modify: `docs/ai_public_component_flow.md`
- Test: 相关 pytest 套件及 Django check。

- [ ] 验证基线、单 B 模式、错误分类、并发默认值。
- [ ] 本地验证后，再在生产为 276 道失败题建立基线并仅重跑缺失 B 模式。
