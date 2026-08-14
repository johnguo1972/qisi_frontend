# A/B/C 模式答案双模型验证与仲裁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让教师手工触发的 A/B/C 模式始终使用完整题面，并通过 Qwen3.7-plus、DeepSeek V4 Pro 两阶段验证与仲裁生成可审计、失败不覆盖旧数据的模式答案。

**Architecture:** 保留现有 API、Celery 任务名和 A/B/C JSON 字段，在公共 AI 层增加完整题目上下文、答案标准化、内容门禁、DeepSeek 验证组件和纯编排仲裁器。现有 `AIReviewService` 负责兼容适配，Celery 任务负责锁、进度与事务保存；DeepSeek 第一阶段看题库答案/解析但不看 Qwen，只有冲突时才把所有候选交给第二阶段。

**Tech Stack:** Python 3、Django 5.2、Django REST Framework、Celery、Redis、Pydantic v2、httpx、pytest、UniApp/Vue 3

**Spec:** `docs/superpowers/specs/2026-08-14-ai-mode-answer-arbitration-design.md`

## Global Constraints

- 所有修改必须位于 `D:\workspace\code\qidi\front`；执行前后都用 `git status --short` 核对路径。
- 不提交 `.env`、dump、媒体文件、`uniapp/dist`、缓存或用户其他未提交改动。
- AI URL 和 API Key 只从 `.env` 读取；不得在代码、测试输出或文档中出现密钥明文。
- 模型路由、参数和提示词只保存在 `config/ai_config.cfg`。
- Qwen A/B/C 使用 `qwen3.7-plus`；DeepSeek 使用现有阿里兼容端点上的 `deepseek-v4-pro`。
- 每次 HTTP 模型请求超时 300 秒；每阶段最多重试一次。
- 单模式 Celery 软超时 3800 秒、硬超时 3900 秒；Redis 重复任务锁 4200 秒并在 `finally` 主动释放。
- A/B/C 及“一键全部 AI 处理”只能由用户手工触发；旧自动生成任务继续保持 tombstone/skip 行为。
- 保持现有 API 地址、响应 envelope、Celery 任务名和 A/B/C 前端字段兼容。
- 实现严格遵循 TDD：每个任务先写失败测试，确认 RED，再做最小实现并确认 GREEN。

## File Structure

### New files

- `apps/common/ai/question_context.py`：把 `ExamQuestion`、有序选项、图片和现有 AI 结果构造成不可变 `QuestionInput`，并计算上下文哈希。
- `apps/common/ai/answer_validation.py`：按题型标准化答案，并执行不调用模型的模式内容质量门禁。
- `apps/common/ai/components/answer_verification.py`：DeepSeek 第一阶段和第二阶段组件。
- `apps/common/ai/answer_arbitration.py`：纯业务仲裁器、决策结果和升级条件。
- `apps/common/ai/tests/test_question_context.py`：完整上下文、选项排序和哈希测试。
- `apps/common/ai/tests/test_answer_validation.py`：答案标准化和内容门禁测试。
- `apps/common/ai/tests/test_answer_verification_components.py`：DeepSeek 两阶段输入隔离与 Schema 测试。
- `apps/common/ai/tests/test_answer_arbitration.py`：全决策表测试。
- `apps/review/ai_mode_dispatch.py`：生成 task ID、Redis 去重锁、重复请求返回和安全释放。

### Modified files

- `apps/common/ai/config.py`：注册新任务并解析 `enable_thinking`、`reasoning_effort`。
- `apps/common/ai/client.py`：把已配置的思考参数放入实际 OpenAI 兼容 payload。
- `apps/common/ai/schemas.py`：增加独立验证和最终复核响应 Schema。
- `apps/common/ai/components/mode_answers.py`：A/B/C 提示变量改为完整上下文，同时保留旧变量。
- `apps/common/ai/components/__init__.py`：导出新组件。
- `apps/common/ai_service.py`：使用上下文构建器和仲裁器，供单模式和完整手工流程共用。
- `apps/review/tasks.py`：单模式超时、原子保存、验证缓存、锁释放和失败保护。
- `apps/review/views.py`：通过去重 dispatcher 派发单模式任务。
- `uniapp/src/components/RightActionPanel.vue`：显示 A/B/C 提交和运行状态并禁用对应按钮。
- `uniapp/src/pages/teacher/question-bank.vue`：收集单模式 task ID、轮询终态并刷新结果。
- `config/ai_config.cfg`：新增 DeepSeek 两阶段任务/提示词，扩展 A/B/C 完整上下文变量，重试改为一次。
- `apps/common/ai/tests/test_config.py`、`test_client.py`、`test_question_components.py`、`test_review_compatibility.py`：配置、payload、兼容和任务回归。
- `apps/review/tests.py`：API 去重与权限/响应契约测试。
- `apps/common/management/commands/ai_smoke_test.py`、`test_smoke_command.py`：允许显式选择新的 DeepSeek验证任务进行安全真实冒烟。
- `docs/ai_process(0801）.md`：记录新 A/B/C 数据流、模型调用条件和失败保护。

---

### Task 1: 配置层和实际思考模式 payload

**Files:**
- Modify: `apps/common/ai/config.py`
- Modify: `apps/common/ai/client.py`
- Modify: `config/ai_config.cfg`
- Test: `apps/common/ai/tests/test_config.py`
- Test: `apps/common/ai/tests/test_client.py`

**Interfaces:**
- Produces: `AITaskConfig.enable_thinking: bool | None`
- Produces: `AITaskConfig.reasoning_effort: str | None`
- Produces task keys: `deepseek_independent_verify`, `deepseek_final_review`
- Consumed later by: DeepSeek components and `AIClient._build_payload()`

- [ ] **Step 1: Write failing configuration tests**

Add tests proving both new tasks route to DeepSeek, use 300 seconds, one retry, and parse thinking fields；同时断言 `mode_a_answer`、`mode_b_answer`、`mode_c_answer` 都从现有三次重试改为一次：

```python
def test_answer_verification_tasks_enable_deepseek_thinking():
    config = AIConfig.load(DEFAULT_AI_CONFIG_PATH)

    for key in ("deepseek_independent_verify", "deepseek_final_review"):
        task = config.get_task_config(key)
        assert task.provider == "deepseek"
        assert task.model == "deepseek-v4-pro"
        assert task.timeout_seconds == 300
        assert task.retry_count == 1
        assert task.enable_thinking is True
        assert task.reasoning_effort == "high"

    for key in ("mode_a_answer", "mode_b_answer", "mode_c_answer"):
        assert config.get_task_config(key).retry_count == 1
```

Add invalid-value tests: `enable_thinking=maybe` and `reasoning_effort=extreme` must raise `AIConfigError` without echoing secrets.

- [ ] **Step 2: Run config tests to verify RED**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_config.py -q
```

Expected: failures because `AITaskConfig` has no thinking fields and the new task keys are unknown.

- [ ] **Step 3: Extend the immutable task configuration**

Add fields with safe defaults so existing test fixtures remain source-compatible:

```python
@dataclass(frozen=True)
class AITaskConfig:
    # existing fields stay unchanged
    response_format: str | None
    enable_thinking: bool | None = None
    reasoning_effort: str | None = None
```

In `_load_task()`, allow optional INI options `enable_thinking` and `reasoning_effort`; parse the former with `_parse_bool_option` only when present and accept only `low`, `medium`, `high` for the latter. Add the two task keys to `TASK_PROVIDER_SCHEMA` with provider `deepseek`.

- [ ] **Step 4: Add new task sections with one retry**

In `config/ai_config.cfg`, add task sections and their complete prompt keys in this same task；Task 4 will bind components and Pydantic schemas to these configured contracts:

```ini
[task:deepseek_independent_verify]
provider = deepseek
model = deepseek-v4-pro
prompt = deepseek_independent_verify
temperature = 0.1
max_tokens = 8192
timeout_seconds = 300
retry_count = 1
retry_backoff_seconds = 2
response_format = json
enable_thinking = true
reasoning_effort = high

[task:deepseek_final_review]
provider = deepseek
model = deepseek-v4-pro
prompt = deepseek_final_review
temperature = 0.1
max_tokens = 8192
timeout_seconds = 300
retry_count = 1
retry_backoff_seconds = 2
response_format = json
enable_thinking = true
reasoning_effort = high
```

In the same edit, set `retry_count = 1` and a single backoff value for the existing `task:mode_a_answer`, `task:mode_b_answer` and `task:mode_c_answer` sections; otherwise the approved 1800-second theoretical model budget is false.

同时加入可直接投入使用的完整 prompt sections：第一阶段明确“题库资料可能错误、先重新求解、不可接收或猜测 Qwen 结果”；第二阶段明确“匿名比较候选、输出可信答案、必要时给出完整目标模式内容”。变量分别固定为 `question_context_json, target_mode, mode_schema_json` 和 `question_context_json, target_mode, qwen_result_json, independent_result_json, conflicts_json, mode_schema_json`。Task 4 只增加 Schema/组件并验证这些既定契约，不再保留临时提示词。

- [ ] **Step 5: Write failing payload tests**

Extend the `test_client.py` fixture factory to accept thinking fields, then capture the DeepSeek request:

```python
assert seen["payload"]["enable_thinking"] is True
assert seen["payload"]["reasoning_effort"] == "high"
```

Also assert Qwen tasks omit both keys when their configuration values are `None`.

- [ ] **Step 6: Run client tests to verify RED**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_client.py -q
```

Expected: DeepSeek payload assertions fail because `_build_payload()` does not emit the fields.

- [ ] **Step 7: Emit configured thinking fields only when present**

In `_build_payload()` add:

```python
if task.enable_thinking is not None:
    payload["enable_thinking"] = task.enable_thinking
if task.reasoning_effort is not None:
    payload["reasoning_effort"] = task.reasoning_effort
```

Do not infer model behavior from model names and do not add these keys to Qwen tasks unless cfg explicitly configures them.

- [ ] **Step 8: Run Task 1 tests and commit**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_config.py apps/common/ai/tests/test_client.py -q
```

Expected: all pass.

Commit:

```powershell
git add apps/common/ai/config.py apps/common/ai/client.py config/ai_config.cfg apps/common/ai/tests/test_config.py apps/common/ai/tests/test_client.py
git commit -m "feat(ai): configure DeepSeek thinking verification"
```

### Task 2: 完整题目上下文和 A/B/C 提示输入

**Files:**
- Create: `apps/common/ai/question_context.py`
- Modify: `apps/common/ai/components/mode_answers.py`
- Modify: `config/ai_config.cfg`
- Test: `apps/common/ai/tests/test_question_context.py`
- Test: `apps/common/ai/tests/test_question_components.py`

**Interfaces:**
- Produces: `QuestionContextBuilder.build(question, *, image_urls=(), normalized_text="", vision_result=None, knowledge_refs="", target_mode="") -> QuestionInput`
- Produces: `question_context_payload(question_input: QuestionInput, *, include_qwen_result=False) -> dict[str, object]`
- Produces: `question_context_hash(question_input: QuestionInput) -> str`
- Consumed later by: A/B/C components, DeepSeek components, arbitration cache

- [ ] **Step 1: Write failing ordered-context tests**

Use a fake question whose `.options.all().order_by()` yields D, B, A, C input rows with explicit `sort_order`. Assert the builder produces A/B/C/D prompt options in stable order and includes:

```python
assert payload["stem"] == "下列各数据中与实际情况不相符的是（ ）"
assert payload["options"] == [
    {"label": "A", "content": "一个中学生的身高约为1.65m"},
    {"label": "B", "content": "人步行的速度约为1.1m/s"},
    {"label": "C", "content": "人最舒适的环境温度是37℃"},
    {"label": "D", "content": "学生课桌的高度约为80cm"},
]
assert payload["reference_answer"] == "C"
assert payload["reference_analysis"]
```

Add tests for `material`, `tables`, `subquestions`, subject/type/difficulty, image URLs, vision facts and empty optional fields.

- [ ] **Step 2: Write failing context hash tests**

Assert identical content gives the same SHA-256 hash; changing stem, an option, reference answer, reference analysis or vision result changes it; changing `target_mode` does not change the shared answer-verification hash.

- [ ] **Step 3: Run context tests to verify RED**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_question_context.py -q
```

Expected: import failure because `question_context.py` does not exist.

- [ ] **Step 4: Implement immutable context building**

Implement `QuestionContextBuilder` without writing to the database. Convert related options to plain dictionaries before constructing `QuestionInput`; store additional fields under `metadata` using stable names:

```python
metadata = {
    "question_type": question.question_type or "",
    "subject": question.subject or "",
    "difficulty": str(question.difficulty or ""),
    "analysis": question.analysis or "",
    "material": question.material or "",
    "tables": question.tables or [],
    "subquestions": question.subquestions or [],
    "normalized_text": normalized_text or question.stem or "",
    "vision_result": vision_result or {},
    "knowledge_refs": knowledge_refs or "",
    "target_mode": target_mode,
}
```

Keep `QuestionInput.answer` for the reference answer and `QuestionInput.solution` for the reference solution. JSON serialization must use `ensure_ascii=False`, sorted keys for the hash, and must not serialize Django model objects or managers.

- [ ] **Step 5: Write failing A/B/C prompt-capture tests**

Use `RecordingAIClient` and assert the rendered user prompt for every mode contains the stem, all four option contents, reference answer `C` and reference analysis. Assert the captured prompt does not contain Python manager representations.

- [ ] **Step 6: Run mode prompt tests to verify RED**

Run the new focused tests in `test_question_components.py`; expect failures because current `_ModeAnswerComponent.prompt_variables()` only emits normalized text, vision and knowledge references.

- [ ] **Step 7: Add `question_context_json` to every mode prompt**

Return the existing three variables plus:

```python
"question_context_json": json.dumps(
    question_context_payload(question),
    ensure_ascii=False,
    sort_keys=True,
)
```

Update each `prompt:mode_*_answer` variable declaration and user template so `question_context_json` is the authoritative full input. Keep the existing variables during migration because other tests and compatibility callers still provide them.

- [ ] **Step 8: Run Task 2 tests and commit**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_question_context.py apps/common/ai/tests/test_question_components.py -q
```

Expected: all pass.

Commit:

```powershell
git add apps/common/ai/question_context.py apps/common/ai/components/mode_answers.py config/ai_config.cfg apps/common/ai/tests/test_question_context.py apps/common/ai/tests/test_question_components.py
git commit -m "fix(ai): send complete question context to mode solvers"
```

### Task 3: 答案标准化与模式内容质量门禁

**Files:**
- Create: `apps/common/ai/answer_validation.py`
- Create: `apps/common/ai/tests/test_answer_validation.py`

**Interfaces:**
- Produces: `NormalizedAnswer(value: str, valid: bool, reason: str = "")`
- Produces: `ContentValidation(valid: bool, issues: tuple[str, ...])`
- Produces: `AnswerNormalizer.normalize(raw, *, question_type, option_labels=()) -> NormalizedAnswer`
- Produces: `ModeContentValidator.validate(mode, result, *, trusted_answer, context) -> ContentValidation`
- Consumed later by: `ModeAnswerArbitrator`

- [ ] **Step 1: Write failing normalization table tests**

Cover at least:

```python
@pytest.mark.parametrize(
    ("raw", "expected"),
    [("c", "C"), ("选C", "C"), ("答案：C", "C"), ("C。", "C")],
)
def test_single_choice_normalization(raw, expected): ...
```

Also cover multi-select `CA`/`A,C` to `AC`, true/false aliases, safe numeric whitespace normalization, blank values, `missing_conditions`, option `E` when only A-D exist, and free-response values that must not be over-normalized.

- [ ] **Step 2: Write failing content-gate tests**

For all modes, reject a result whose `final_answer` differs from `trusted_answer`. For Mode A reject non-empty `missing_conditions` when the context has complete options. Reject text containing “未提供选项” or “没有提供选项” in a complete choice question. Preserve valid existing Mode A/B/C shapes.

- [ ] **Step 3: Run tests to verify RED**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_answer_validation.py -q
```

Expected: import failure.

- [ ] **Step 4: Implement conservative normalization**

Implement deterministic parsing only for recognized question types. `missing_conditions` must produce `valid=False`; an unknown subjective answer remains trimmed text rather than being converted to an option. Never use substring matching that turns arbitrary prose containing “A” into option A.

- [ ] **Step 5: Implement structural content validation**

Recursively collect visible strings from the result, compare normalized final answers, and emit stable issue codes such as:

```python
"invalid_final_answer"
"final_answer_conflict"
"false_missing_conditions"
"claims_options_missing"
"mode_schema_incomplete"
```

Do not attempt to prove semantic correctness locally; return an issue requiring final review when deterministic checks cannot establish consistency.

- [ ] **Step 6: Run Task 3 tests and commit**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_answer_validation.py -q
```

Expected: all pass.

Commit:

```powershell
git add apps/common/ai/answer_validation.py apps/common/ai/tests/test_answer_validation.py
git commit -m "feat(ai): normalize and validate mode answers"
```

### Task 4: DeepSeek 第一阶段与第二阶段公共组件

**Files:**
- Create: `apps/common/ai/components/answer_verification.py`
- Modify: `apps/common/ai/components/__init__.py`
- Modify: `apps/common/ai/schemas.py`
- Modify: `config/ai_config.cfg`
- Test: `apps/common/ai/tests/test_answer_verification_components.py`

**Interfaces:**
- Produces: `DeepSeekIndependentVerifierComponent.run(QuestionInput) -> dict`
- Produces: `DeepSeekFinalReviewComponent.run(QuestionInput) -> dict`
- First-stage metadata inputs: `target_mode`, full question context; no `qwen_result`
- Second-stage metadata inputs: `target_mode`, `qwen_result`, `independent_result`, `conflicts`
- Consumed later by: `ModeAnswerArbitrator` and `AIReviewService`

- [ ] **Step 1: Write failing first-stage isolation tests**

Build a `QuestionInput` containing reference answer/analysis and deliberately place a Qwen marker in metadata. Assert the first-stage rendered prompt contains the reference answer and analysis but never contains the Qwen marker or a `qwen_result` field.

- [ ] **Step 2: Write failing second-stage completeness tests**

Assert the second-stage rendered prompt contains the full question, anonymized Qwen candidate, independent result and conflict codes. Verify malformed responses fail Pydantic validation.

- [ ] **Step 3: Run tests to verify RED**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_answer_verification_components.py -q
```

Expected: imports fail because components and schemas do not exist.

- [ ] **Step 4: Add strict response schemas**

Define Pydantic models with these required contracts:

```python
class IndependentVerificationResponse(_StrictResponseModel):
    independent_answer: NonBlankStr
    independent_reasoning_summary: NonBlankStr
    key_facts: list[NonBlankStr]
    reference_answer_valid: bool | None
    reference_analysis_valid: bool | None
    reference_issues: list[str]
    confidence: float = Field(ge=0, le=1)
    mode_content: dict[str, Any]

class FinalReviewResponse(_StrictResponseModel):
    trusted_answer: NonBlankStr
    qwen_content_valid: bool
    candidate_issues: list[NonBlankStr]
    confidence: float = Field(ge=0, le=1)
    mode_content: dict[str, Any]
```

Allow `None` for reference-validity fields only when the question truly has no reference answer/analysis.

- [ ] **Step 5: Implement prompt variables with hard isolation**

`DeepSeekIndependentVerifierComponent.prompt_variables()` must create its JSON from `question_context_payload()` and explicitly discard `qwen_result`, `independent_result` and `conflicts`, even if callers accidentally include them.

`DeepSeekFinalReviewComponent.prompt_variables()` must anonymize candidate labels and serialize only plain data. Both components use `QuestionAIComponent.run()` and their fixed task keys.

- [ ] **Step 6: Verify and finalize the configured prompt contracts**

确认 Task 1 写入的第一阶段 prompt 明确包含：

```text
题库答案和解析是待验证参考资料，可能错误。先依据题面重新求解，再判断参考答案和解析；你看不到且不得猜测Qwen结果。返回严格JSON，不输出隐藏思考过程。
```

确认第二阶段 prompt 明确包含：

```text
根据题面、参考资料、候选甲和独立验证结果裁决。指出冲突，返回可信答案；若候选甲内容不可采用，必须在mode_content中给出目标模式的完整替代内容。返回严格JSON。
```

Declare exact variables:

```ini
variables = question_context_json, target_mode, mode_schema_json
```

and:

```ini
variables = question_context_json, target_mode, qwen_result_json, independent_result_json, conflicts_json, mode_schema_json
```

- [ ] **Step 7: Run Task 4 tests and commit**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_answer_verification_components.py apps/common/ai/tests/test_config.py -q
```

Expected: all pass.

Commit:

```powershell
git add apps/common/ai/components/answer_verification.py apps/common/ai/components/__init__.py apps/common/ai/schemas.py config/ai_config.cfg apps/common/ai/tests/test_answer_verification_components.py
git commit -m "feat(ai): add two-stage DeepSeek answer verification"
```

### Task 5: 纯业务答案仲裁器

**Files:**
- Create: `apps/common/ai/answer_arbitration.py`
- Create: `apps/common/ai/tests/test_answer_arbitration.py`

**Interfaces:**
- Consumes: `QuestionInput`, `AnswerNormalizer`, `ModeContentValidator`
- Consumes callables: `generate(mode, context)`, `independent_verify(mode, context)`, `final_review(mode, context, qwen_result, independent_result, conflicts)`
- Produces: `ArbitrationOutcome(answer: dict, verification: dict, shared_verifier_result: dict | None)`
- Produces: `ModeAnswerArbitrator.process(mode, context, *, cached_verification=None) -> ArbitrationOutcome`
- Consumed later by: `AIReviewService`

- [ ] **Step 1: Write the full failing decision table**

Use injected recording callables and cover:

```text
R=Q valid                    -> Qwen only
R=Q but content invalid      -> DeepSeek first stage; final review if needed
Q!=R and D=R                 -> DeepSeek candidate, not Qwen
Q!=R and D=Q                 -> Qwen only when content/key-fact gates pass
R,Q,D all different          -> final review required
no R and Q=D                 -> Qwen when content valid
no R and Q!=D                -> final review required
low DeepSeek confidence      -> final review required
reference answer valid but reference analysis invalid -> final review
```

For every row assert exact provider call counts and that first-stage input does not contain Qwen output.

- [ ] **Step 2: Write failing cache tests**

Pass a cached first-stage result with matching `context_hash`; assert the independent verifier is not called. Change the context hash and assert it is called. Cached mode content must never be reused across A/B/C；如果当前模式最终需要 DeepSeek 内容而缓存只含其他模式候选，必须调用第二阶段为当前模式生成内容。

- [ ] **Step 3: Write failing failure-closed tests**

If required independent or final review raises `AIRequestError`, assert `process()` raises a stable arbitration exception and returns no savable answer. If DeepSeek reports genuine missing conditions, assert the result is flagged for human review rather than selecting Qwen.

- [ ] **Step 4: Run tests to verify RED**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_answer_arbitration.py -q
```

Expected: import failure.

- [ ] **Step 5: Implement the smallest deterministic state machine**

Use explicit branches rather than a scoring heuristic. Build verification data with stable keys:

```python
verification = {
    "status": "accepted",
    "context_hash": context_hash,
    "reference_answer": normalized_r.value,
    "qwen_answer": normalized_q.value,
    "deepseek_answer": normalized_d.value if normalized_d else "",
    "trusted_answer": trusted_answer,
    "selected_content_provider": provider,
    "deepseek_thinking_enabled": deepseek_used,
    "final_review_used": final_review_used,
    "confidence": confidence,
    "warnings": warnings,
}
```

The outcome answer must keep the original mode payload and add `verification`; it must not add hidden reasoning content. 缓存命中时只复用 `independent_answer`、参考资料判断、关键事实、置信度和哈希；先丢弃缓存中的 `mode_content`，避免把 A 模式候选写入 B/C。

- [ ] **Step 6: Run Task 5 tests and commit**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_answer_arbitration.py -q
```

Expected: all pass.

Commit:

```powershell
git add apps/common/ai/answer_arbitration.py apps/common/ai/tests/test_answer_arbitration.py
git commit -m "feat(ai): arbitrate Qwen and DeepSeek mode answers"
```

### Task 6: 接入 `AIReviewService`、完整手工流程和共享验证缓存

**Files:**
- Modify: `apps/common/ai_service.py`
- Modify: `apps/common/ai/tests/test_review_compatibility.py`
- Modify: `apps/common/ai/tests/test_question_components.py`

**Interfaces:**
- Consumes: `QuestionContextBuilder`, `ModeAnswerArbitrator`, new DeepSeek components
- Produces: `AIReviewService.solve_mode_with_arbitration(question, *, mode, image_urls, normalized_text, vision_result, knowledge_refs, cached_verification=None) -> ArbitrationOutcome`
- Preserves: existing `solve_mode_a/b/c()` methods for non-orchestrating compatibility callers
- Consumed later by: `single_mode_ai_process_question`、`process_question_full` 和 `process_question_full_v2`

- [ ] **Step 1: Write failing service integration tests**

Use a real `QuestionOption` database fixture and an injected fake component factory. Assert `solve_mode_with_arbitration()` sends all options, `answer`, `analysis`, `solution`, tables and images. Assert the mode route model remains `qwen3.7-plus` unless an existing supported override is explicitly provided.

- [ ] **Step 2: Write failing full-manual-pipeline tests**

Patch all model calls and分别运行 `process_question_full()`（批量AI/一键全部入口）与 `process_question_full_v2()`（单题完整入口）。Assert A/B/C each pass through the arbitrator and receive their own verification nodes. Assert legacy automatic task tests still return `automatic_generation_disabled` and make no facade.

- [ ] **Step 3: Run focused tests to verify RED**

Run:

```powershell
python -m pytest apps/common/ai/tests/test_review_compatibility.py -k "arbitration or full" --reuse-db -q
```

Expected: failures because the service method does not exist and full v2 still calls raw solvers.

- [ ] **Step 4: Construct shared components once per service**

Add lazy/injected dependencies without creating a second HTTP client. The service must obtain all mode and DeepSeek components from its existing `QuestionComponentFactory`, then pass callables into `ModeAnswerArbitrator`.

- [ ] **Step 5: Build context through `QuestionContextBuilder`**

Replace the current `_question_input()` handling of `question.options` managers with the builder for mode paths. Do not change probe, vision or unrelated guidance semantics except where necessary to preserve the existing `QuestionInput` signature.

- [ ] **Step 6: Route all manually-triggered A/B/C generation through arbitration**

Add `solve_mode_with_arbitration()` and use it from the single-mode task integration point、`process_question_full()` 与 `process_question_full_v2()`。Within one full run, carry the matching `shared_verifier_result` from A to B to C when the context hash is unchanged；任何模式仲裁失败时，该模式不得出现在可持久化成功结果中。

- [ ] **Step 7: Run compatibility tests and commit**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_question_components.py -q
python -m pytest apps/common/ai/tests/test_review_compatibility.py --reuse-db -q
```

Expected: all pass, including automatic-generation-disabled regressions.

Commit:

```powershell
git add apps/common/ai_service.py apps/common/ai/tests/test_review_compatibility.py apps/common/ai/tests/test_question_components.py
git commit -m "refactor(review): route manual mode answers through arbitration"
```

### Task 7: Celery去重、3800/3900超时、原子保存与失败保护

**Files:**
- Create: `apps/review/ai_mode_dispatch.py`
- Modify: `apps/review/views.py`
- Modify: `apps/review/tasks.py`
- Modify: `apps/review/tests.py`
- Modify: `apps/common/ai/tests/test_review_compatibility.py`
- Modify: `uniapp/src/components/RightActionPanel.vue`
- Modify: `uniapp/src/pages/teacher/question-bank.vue`

**Interfaces:**
- Produces: `dispatch_single_mode_ai_task(question_id: str, mode: str, model: str | None) -> ModeTaskDispatch`
- Produces: `ModeTaskDispatch(task_id: str, status: Literal["pending", "running"], created: bool)`
- Produces lock key: `ai-mode-lock:{question_id}:{mode}` with 4200-second TTL
- Task consumes the pre-generated Celery task ID and releases only its matching lock in `finally`

- [ ] **Step 1: Write failing dispatcher deduplication tests**

Patch `cache.add`, `cache.get` and `single_mode_ai_process_question.apply_async`. First call must generate a UUID, acquire the lock, enqueue with that exact `task_id`, and return `created=True`. A second call must return the stored task ID with `created=False` and must not enqueue.

- [ ] **Step 2: Write failing enqueue-failure and release tests**

If `apply_async` raises, the dispatcher must delete its own lock before re-raising. For task success, handled failure and unexpected exception, assert the matching lock is released in `finally`. Assert a mismatched/newer task ID is never deleted.

- [ ] **Step 3: Write failing timeout and atomicity tests**

Assert Celery task options expose:

```python
assert single_mode_ai_process_question.soft_time_limit == 3800
assert single_mode_ai_process_question.time_limit == 3900
```

Start with an old `ai_answer_a`, make arbitration fail, refresh from DB and assert the old JSON remains byte-for-byte equal. On success assert `ai_answer_a`, `ai_verifier_result`, `ai_processed_at` and status update in one `transaction.atomic()` block.

- [ ] **Step 4: Run focused tests to verify RED**

Run:

```powershell
python -m pytest apps/review/tests.py apps/common/ai/tests/test_review_compatibility.py -k "dispatch or lock or single_mode or failure" --reuse-db -q
```

Expected: failures because dispatcher, limits and atomic persistence are absent.

- [ ] **Step 5: Implement task dispatch ownership**

Store a small JSON value containing `task_id` under the lock key with TTL 4200. Use `apply_async(..., task_id=task_id)` so the API can return a stable task ID before enqueueing. The duplicate response remains HTTP 200 with the existing envelope and adds only compatible data:

```json
{"task_id": "...", "status": "running", "mode": "A", "deduplicated": true}
```

- [ ] **Step 6: Apply task limits and safe release**

Decorate the single-mode task with `soft_time_limit=3800` and `time_limit=3900`. Put service close and lock release in `finally`; do not expose provider response text in progress errors or logs.

- [ ] **Step 7: Persist only completed arbitration outcomes**

Inside `transaction.atomic()`, refetch the question with `select_for_update()`, set only the requested mode field, update `ai_verifier_result` with the shared result, and update processing metadata. Do not set `ai_processing_status='success'` before all required validation succeeds.

- [ ] **Step 8: Route the API through the dispatcher**

Keep mode validation, authentication/permission behavior and not-found handling. Replace direct `.delay()` with `dispatch_single_mode_ai_task()` and preserve the existing `success/data` envelope.

- [ ] **Step 9: Show and poll the real A/B/C running state in the teacher bank**

Add an `aiModeRunning` reactive map keyed by A/B/C in `question-bank.vue`. `handleAiMode()` must collect every returned task ID, poll `questionApi.getTaskStatus(taskId)` until `complete`, `partial`, `failed` or `skipped`, refresh the question list after success, and clear the matching flag in `finally`. Pass the active mode to `RightActionPanel`；the component disables only the matching mode button and renders `AI-A处理中...`、`AI-B处理中...` or `AI-C处理中...`. Do not trigger any status request merely from opening or refreshing the page.

- [ ] **Step 10: Run Task 7 tests and build, then commit**

Run:

```powershell
python -m pytest apps/review/tests.py apps/common/ai/tests/test_review_compatibility.py --reuse-db -q
Set-Location uniapp
npm run build:h5
Set-Location ..
```

Expected: all pass.

Commit:

```powershell
git add apps/review/ai_mode_dispatch.py apps/review/views.py apps/review/tasks.py apps/review/tests.py apps/common/ai/tests/test_review_compatibility.py uniapp/src/components/RightActionPanel.vue uniapp/src/pages/teacher/question-bank.vue
git commit -m "fix(review): protect manual AI mode task execution"
```

### Task 8: 回归、真实模型测试、教师页面端到端验收与文档

**Files:**
- Modify: `apps/common/management/commands/ai_smoke_test.py`
- Modify: `apps/common/ai/tests/test_smoke_command.py`
- Modify: `docs/ai_process(0801）.md`
- Test/verify: all files changed in Tasks 1-7

**Interfaces:**
- Produces safe command selection for `deepseek_independent_verify` and `deepseek_final_review`
- Produces final evidence separating automated, simulated, live-provider and browser E2E results

- [ ] **Step 1: Write failing smoke-command selection tests**

Add a `--task` choice limited to safe configured smoke tasks. Assert `--provider deepseek --task deepseek_independent_verify --live` uses that task, reports only provider/model/latency/schema status, and never prints prompt, reference answer, API Key or raw response.

- [ ] **Step 2: Run smoke command tests to verify RED**

Run:

```powershell
python -m pytest --noconftest apps/common/ai/tests/test_smoke_command.py -q
```

Expected: failure because `--task` is unsupported.

- [ ] **Step 3: Add safe explicit task selection and update documentation**

Implement an allowlist mapping rather than accepting arbitrary task keys. Update `docs/ai_process(0801）.md` with:

- complete context fields;
- Qwen fast path;
- DeepSeek first-stage inputs including reference answer/analysis but excluding Qwen;
- second-stage escalation rules;
- context hash reuse;
- 300-second request timeout, 3800/3900 task limits and 4200-second lock;
- failure-closed persistence and manual-trigger-only behavior.

- [ ] **Step 4: Run complete automated regression**

Run:

```powershell
python manage.py check
python -m pytest --noconftest apps/common/ai/tests -q
python -m pytest apps/review/tests.py apps/common/ai/tests/test_review_compatibility.py --reuse-db -q
```

Expected: Django reports no system-check issues and all tests pass. If the shared test database is locked, record that separately and rerun database-free suites; do not describe DB integration as passed until it actually runs.

- [ ] **Step 5: Build the H5 frontend**

Run:

```powershell
Set-Location uniapp
npm run build:h5
Set-Location ..
```

Expected: production build exits 0. Do not stage `uniapp/dist`.

- [ ] **Step 6: Run explicitly authorized live provider smoke checks**

Using the existing local `.env` without printing it:

```powershell
python manage.py ai_smoke_test --provider qwen --live
python manage.py ai_smoke_test --provider deepseek --task deepseek_independent_verify --live
```

Expected: both commands report provider/model/latency and valid schema only. A provider/network failure must be reported as external evidence, separate from code-test failures.

- [ ] **Step 7: Back up and exercise the target question through real APIs**

For UUID `019fa8a0-9397-7101-8180-545551f3f33f`, save the current `ai_answer_a/b/c` and `ai_verifier_result` values to an in-memory test fixture or a temporary file under an ignored `front` temp directory. Verify the database row has answer `C`, its reference analysis, and four options before triggering.

Through an authenticated teacher account, manually invoke A, then B, then C and poll the existing task-status API. Verify:

```text
final_answer = C
no missing_conditions
no “没有提供选项”
explanation distinguishes 37℃ body temperature from comfortable ambient temperature
each mode writes only its own field
verification records provider selection and final_review_used
```

Restore the backed-up JSON only if the live test cannot complete and the test itself left a partial/non-production result; do not overwrite a newly validated successful result.

- [ ] **Step 8: Verify the real teacher page in H5**

Start Django, Celery and `npm run dev:h5`; log in as a teacher or administrator+teacher. In the browser select the target question and click A/B/C separately. Verify button busy state, duplicate-click behavior, task progress, modal content, refresh persistence and failure messages. Confirm no AI task starts merely from opening or refreshing the page.

- [ ] **Step 9: Run secret/artifact and scope checks**

Run:

```powershell
git diff --check
git status --short
git diff --name-only
```

Inspect every changed path. Confirm `.env`, dump, media, `uniapp/dist`, `.pytest_cache`, `__pycache__` and unrelated `docs/improve.md` are not staged.

- [ ] **Step 10: Commit documentation and smoke-test support**

```powershell
git add apps/common/management/commands/ai_smoke_test.py apps/common/ai/tests/test_smoke_command.py 'docs/ai_process(0801）.md'
git commit -m "test(ai): verify mode answer arbitration end to end"
```

- [ ] **Step 11: Final evidence report**

Report separately:

1. automated unit/component test counts;
2. database integration results;
3. Django check and H5 build;
4. Qwen and DeepSeek live smoke results;
5. target-question API results for A/B/C;
6. teacher-page browser E2E results;
7. any external provider or local-service blockers.

Do not use “端到端完成” unless items 1-6 all have current-run evidence.

## Plan Completion Checklist

- [ ] Every implementation commit contains only intended `front` files.
- [ ] No old automatic AI path is re-enabled.
- [ ] DeepSeek first stage contains reference answer/analysis but no Qwen result.
- [ ] Second stage runs only on conflict/low confidence/content failure.
- [ ] `enable_thinking=true` and `reasoning_effort=high` are proven in captured payload.
- [ ] 300/3800/3900/4200 second values are covered by tests.
- [ ] Existing successful mode data survives every required-stage failure.
- [ ] Target question returns answer C with a factually correct explanation in A/B/C.
