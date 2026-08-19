# 无答案题目 AI 仲裁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为无答案题目建立 DeepSeek 基准答案/解析，并以该基准安全仲裁 Qwen 的 A、B、C 模式输出。

**Architecture:** 服务层根据题目答案是否为空选择仲裁策略。无答案策略先创建并持久化 DeepSeek 基准解答，然后按模式执行 Qwen 生成、答案比较、必要的最终复核与一次重试；每一步通过既有 `on_step_complete` 回调立即持久化。

**Tech Stack:** Django 5、Pydantic Schema、Celery、Redis、pytest、Qwen、DeepSeek。

**Spec:** `docs/superpowers/specs/2026-08-19-unanswered-question-ai-arbitration-design.md`

## Global Constraints

- 仅修改 `front/` 目录及本独立 worktree。
- 不修改 `.env`，不记录模型原始响应、思考链、API Key 或题目敏感内容。
- DeepSeek 单请求超时保持 300 秒；单模式 Celery 安全上限保持现有 3800/3900 秒。
- 每个步骤完成即保存；失败不得回滚已保存步骤。
- 所有生产改动必须先有可观察的失败测试。

---

### Task 1: 基准答案与解析契约

**Files:**
- Modify: `apps/common/ai/schemas.py`
- Modify: `apps/common/ai/components/answer_verification.py`
- Modify: `apps/common/ai_service.py`
- Test: `apps/common/ai/tests/test_answer_verification_components.py`
- Test: `apps/common/ai/tests/test_review_compatibility.py`

**Interfaces:**
- Produces `AIReviewService.solve_unanswered_question_baseline(question, *, image_urls, normalized_text, vision_result, knowledge_refs) -> dict`.
- Result keys are `canonical_answer`, `canonical_analysis`, `confidence`, `key_facts`, and `context_hash`.

- [ ] **Step 1: Write failing component/schema tests**

```python
def test_unanswered_baseline_requires_answer_and_analysis():
    result = component.run(question_input)
    assert result["canonical_answer"] == "C"
    assert result["canonical_analysis"]

def test_unanswered_baseline_rejects_blank_analysis():
    with pytest.raises(AIResponseError):
        component.run(question_input)
```

- [ ] **Step 2: Run RED tests**

Run: `python -m pytest apps/common/ai/tests/test_answer_verification_components.py -k unanswered_baseline -q`

Expected: FAIL because the baseline Schema/component/service API does not exist.

- [ ] **Step 3: Implement the strict baseline response and service method**

```python
baseline = {
    "canonical_answer": response.independent_answer,
    "canonical_analysis": response.independent_reasoning_summary,
    "confidence": response.confidence,
    "key_facts": response.key_facts,
    "context_hash": question_context_hash(context),
}
```

Create `DeepSeekBaselineSolveComponent` with a dedicated `deepseek_baseline_solve` task and prompt; require nonblank answer and analysis and `confidence >= 0.80`. The component must send no target-mode schema and must request no A/B/C mode content.

- [ ] **Step 4: Run GREEN tests**

Run the Step 2 command and the affected compatibility tests. Expected: PASS.

### Task 2: 无答案模式仲裁与一次重试

**Files:**
- Modify: `apps/common/ai/answer_arbitration.py`
- Modify: `apps/common/ai_service.py`
- Test: `apps/common/ai/tests/test_answer_arbitration.py`
- Test: `apps/common/ai/tests/test_review_compatibility.py`

**Interfaces:**
- Consumes the Task 1 baseline result.
- Produces a validated mode answer or `answer_mismatch_after_retry` without blocking later modes.

- [ ] **Step 1: Write failing arbitration tests**

```python
def test_unanswered_mode_accepts_schema_valid_qwen_when_final_answer_matches_baseline():
    outcome = arbitrator.process_unanswered("B", context, baseline)
    assert outcome.verification["selected_content_provider"] == "qwen"

def test_unanswered_mode_retries_once_after_final_review_rejects_mismatch():
    outcome = arbitrator.process_unanswered("B", context, baseline)
    assert calls.generate_count == 2

def test_unanswered_mode_records_error_after_second_rejected_mismatch():
    with pytest.raises(ArbitrationProviderError, match="answer_mismatch_after_retry"):
        arbitrator.process_unanswered("B", context, baseline)
```

- [ ] **Step 2: Run RED tests**

Run: `python -m pytest apps/common/ai/tests/test_answer_arbitration.py -k unanswered_mode -q`

Expected: FAIL because the unanswered strategy does not exist.

- [ ] **Step 3: Implement mode-only answer comparison**

Normalize only `final_answer`; bypass process/text comparison. On a mismatch call the existing DeepSeek final-review component with the baseline answer/analysis and current Qwen mode content. Retry only the current Qwen mode once after a rejection.

- [ ] **Step 4: Run GREEN tests**

Run the Step 2 command and all arbitration tests. Expected: PASS.

### Task 3: 逐步持久化、任务错误分类与回归

**Files:**
- Modify: `apps/common/ai_service.py`
- Modify: `apps/review/tasks.py`
- Modify: `apps/review/tests.py`
- Test: `apps/common/ai/tests/test_review_compatibility.py`
- Test: `apps/review/tests.py`

**Interfaces:**
- `process_question_full_v2` emits `baseline` and then `answer_a`/`answer_b`/`answer_c` through `on_step_complete`.
- `save_results_to_question` writes baseline answer/analysis atomically before mode results.

- [ ] **Step 1: Write failing persistence tests**

```python
def test_unanswered_pipeline_saves_baseline_before_mode_b_failure():
    results = service.process_question_full_v2(question.id, on_step_complete=save)
    assert question.answer == "C"
    assert question.analysis
    assert results["errors"] == {"answer_b": "answer_mismatch_after_retry"}
```

- [ ] **Step 2: Run RED tests**

Run: `python -m pytest apps/review/tests.py -k unanswered_pipeline -q --reuse-db`

Expected: FAIL because baseline is not persisted before mode execution.

- [ ] **Step 3: Implement immediate persistence and safe error codes**

Call `on_step_complete("baseline", baseline)` immediately after DeepSeek succeeds. Extend `save_results_to_question` to write `answer`, `analysis`, and an allowlisted verifier envelope. Preserve already-completed A/C results when B fails.

- [ ] **Step 4: Run GREEN and regression tests**

Run:

```powershell
python -m pytest apps/common/ai/tests/test_answer_arbitration.py apps/common/ai/tests/test_answer_verification_components.py apps/common/ai/tests/test_review_compatibility.py apps/review/tests.py -q --reuse-db
python manage.py check
```

Expected: PASS and no Django system-check errors.

### Task 4: 本地小规模真实验证

**Files:**
- No committed production file required.

- [ ] **Step 1: Select four local questions with saved probe results**

Query only questions with nonblank `ai_probe_result`; record only UUID、题型和结果状态。

- [ ] **Step 2: Execute 1/2/4 concurrent B-mode local calls**

Use the persisted probe output, capture only elapsed time, terminal status, and safe error category.

- [ ] **Step 3: Verify persistence**

For each successful no-answer question, verify `answer` and `analysis` are nonblank and the B result has a validated final answer.

- [ ] **Step 4: Report results without deployment**

Do not touch production. Report success/failure counts, elapsed time, and classified failures.
