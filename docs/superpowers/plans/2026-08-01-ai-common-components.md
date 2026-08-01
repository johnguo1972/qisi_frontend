# AI 公共组件实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持现有前端 API、Celery 任务名、数据库字段和 JSON 契约不变的前提下，将 `front/` 内所有大模型调用迁移到统一公共 AI 内核，完成 Qwen 3.7 模型升级，保留 DeepSeek 变式题校验，并删除旧直连代码。

**Architecture:** 新增 `apps/common/ai/` 四层结构：配置与提示词注册、统一客户端与响应解析、业务组件、旧接口兼容适配。业务调用只能经由组件进入统一客户端；`.env` 只承载连接地址和密钥，`config/ai_config.cfg` 承载模型路由、参数和全部提示词。

**Tech Stack:** Python 3、Django 5、Celery、httpx、Pydantic 2、ConfigParser、pytest、pytest-django、unittest.mock。

## 全局约束

- 所有修改只能位于 `D:\workspace\code\qidi\front`。
- 不提交 `.env`、数据库 dump、`media/`、`.superpowers/` 临时目录或用户已有的无关修改。
- 不改变 URL、请求参数、响应 envelope、Celery task 名称、数据库字段和前端依赖的 A/B/C JSON 字段。
- 不在日志、测试快照或异常文本中输出 API Key、完整 base64 图片、手机号等敏感信息。
- 每个迁移域先写失败测试，再实现，再执行定向回归；全域切换完成前不删除旧实现。
- 真实模型测试仅各发起一次最小 Qwen 与 DeepSeek 请求，并将供应商/网络失败与代码失败分开报告。

---

## Task 1：建立 AI 调用现状基线文档

**Files:**

- Create: `docs/ai_process(0801）.md`
- Test: `tests/test_ai_architecture_inventory.py`

- [ ] **Step 1：编写会失败的文档完整性测试**

```python
from pathlib import Path


DOC = Path(__file__).parents[1] / "docs" / "ai_process(0801）.md"


def test_ai_process_document_covers_all_active_domains():
    text = DOC.read_text(encoding="utf-8")
    for marker in (
        "AIReviewService", "题目探查", "A 模式", "B 模式", "C 模式",
        "学生引导", "教师引导", "拍照识题", "试卷解析", "变式题",
        "DeepSeek", "持久化", "异常与重试",
    ):
        assert marker in text
```

- [ ] **Step 2：运行测试，确认因文档不存在而失败**

Run: `python -m pytest tests/test_ai_architecture_inventory.py -q`

Expected: FAIL，提示 `docs/ai_process(0801）.md` 不存在。

- [ ] **Step 3：编写现状与目标调用链文档**

文档按调用入口逐项记录：入口文件/函数、输入、提示词来源、模型、HTTP 客户端、解析、持久化、失败策略、迁移后的公共组件。至少覆盖：

```text
common/review -> Probe + ModeA/B/C + ResultVerifier
study -> Guidance + ModeC fallback
missions -> Guidance evaluation
study/photo -> VisionParser
parser -> VisionParser(position/page/question)
courses -> VariantGenerator -> DeepSeek ResultVerifier
```

另附配置职责表、模型路由表、兼容契约表和旧代码删除清单。

- [ ] **Step 4：运行测试确认通过**

Run: `python -m pytest tests/test_ai_architecture_inventory.py -q`

Expected: PASS。

- [ ] **Step 5：提交基线文档与测试**

```powershell
git add -- "docs/ai_process(0801）.md" tests/test_ai_architecture_inventory.py
git commit -m "docs: inventory all AI processing flows"
```

---

## Task 2：实现启动期 AI 配置加载与严格校验

**Files:**

- Create: `config/ai_config.cfg`
- Create: `apps/common/apps.py`
- Create: `apps/common/ai/__init__.py`
- Create: `apps/common/ai/exceptions.py`
- Create: `apps/common/ai/config.py`
- Create: `apps/common/ai/tests/__init__.py`
- Create: `apps/common/ai/tests/test_config.py`
- Modify: `apps/common/__init__.py`
- Modify: `apps/common/exceptions.py`
- Modify: `config/settings.py`

- [ ] **Step 1：为配置 DTO、环境变量和错误场景写失败测试**

```python
def test_loads_task_and_provider_from_cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/chat/completions")
    cfg = write_minimal_cfg(tmp_path, task="question_probe")
    loaded = AIConfig.load(cfg)
    assert loaded.get_task_config("question_probe").model == "qwen3.7-flash"
    assert loaded.get_provider_config("qwen").api_url.endswith("chat/completions")


def test_missing_required_env_fails_without_leaking_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("QWEN_API_KEY", raising=False)
    with pytest.raises(AIConfigError, match="QWEN_API_KEY"):
        AIConfig.load(write_minimal_cfg(tmp_path))
```

同时覆盖：缺 section、非法整数/浮点范围、未知 provider、非法 task model、提示词 section 缺失、UTF-8 中文读取。

- [ ] **Step 2：运行配置测试确认失败**

Run: `python -m pytest apps/common/ai/tests/test_config.py -q`

Expected: FAIL，因 `apps.common.ai.config` 尚不存在。

- [ ] **Step 3：实现配置类型与加载器**

```python
@dataclass(frozen=True)
class AIProviderConfig:
    name: str
    api_url: str
    api_key: str


@dataclass(frozen=True)
class AITaskConfig:
    key: str
    provider: str
    model: str
    prompt: str
    temperature: float
    max_tokens: int
    timeout_seconds: float
    retry_count: int
    retry_backoff_seconds: tuple[float, ...]
    response_format: str | None


class AIConfig:
    @classmethod
    def load(cls, path: Path | None = None) -> "AIConfig": ...
    def get_task_config(self, task_key: str) -> AITaskConfig: ...
    def get_provider_config(self, provider: str) -> AIProviderConfig: ...
```

使用 `RawConfigParser(interpolation=None)`，避免提示词花括号被插值。URL/Key 只能经环境变量名解析；cfg 不得存密钥值。

`apps/common/ai/exceptions.py` 定义 `AIConfigError`、`AIPromptError`、`AIResponseError`；`apps/common/exceptions.py` 继续导出原 `AIRequestError`，并兼容重导出新异常，避免现有 import 失效。

- [ ] **Step 4：建立完整 cfg 骨架和模型映射**

建立任务键：`question_probe`、`knowledge_analysis`、`mode_a_answer`、`mode_b_answer`、`mode_c_answer`、`result_verify`、`vision_fact_extract`、`vision_page_parse`、`vision_question_parse`、`vision_position_detect`、`guidance_generate`、`guidance_evaluate`、`teacher_guidance_evaluate`、`variant_generate`、`variant_verify_deepseek`、`photo_recognize`。

模型限定为 `qwen3.7-flash`、`qwen3.7-plus`、`qwen3-vl-plus` 和 DeepSeek 配置值；不得出现 Qwen 3.6。

- [ ] **Step 5：接入 Django 启动校验**

在 `CommonConfig.ready()` 中调用幂等的 `load_ai_config()`；`INSTALLED_APPS` 改为 `apps.common.apps.CommonConfig`。测试可通过 `reset_ai_config_for_tests()` 清理缓存，但生产运行中不热加载。

- [ ] **Step 6：运行测试和 Django 检查**

Run: `python -m pytest apps/common/ai/tests/test_config.py -q`

Expected: PASS。

Run: `python manage.py check`

Expected: `System check identified no issues`。

- [ ] **Step 7：提交配置层**

```powershell
git add -- config/ai_config.cfg config/settings.py apps/common/__init__.py apps/common/apps.py apps/common/exceptions.py apps/common/ai
git commit -m "feat: add validated AI runtime configuration"
```

---

## Task 3：实现 PromptRegistry 与统一响应解析

**Files:**

- Create: `apps/common/ai/prompt_registry.py`
- Create: `apps/common/ai/response_parser.py`
- Create: `apps/common/ai/schemas.py`
- Create: `apps/common/ai/tests/test_prompt_registry.py`
- Create: `apps/common/ai/tests/test_response_parser.py`
- Modify: `config/ai_config.cfg`

- [ ] **Step 1：写提示词渲染和 JSON 解析失败测试**

```python
def test_prompt_registry_rejects_missing_variable(registry):
    with pytest.raises(AIPromptError, match="stem"):
        registry.render("mode_a_answer", figure_facts="{}")


def test_response_parser_repairs_fenced_json():
    parsed = ResponseParser.parse_json("```json\n{\"answer\":\"D\",}\n```")
    assert parsed == {"answer": "D"}
```

覆盖未知变量、未替换占位符、尾逗号、数组顶层、choices 缺失、不可恢复 JSON、Pydantic Schema 错误以及原始响应截断。

- [ ] **Step 2：运行测试确认失败**

Run: `python -m pytest apps/common/ai/tests/test_prompt_registry.py apps/common/ai/tests/test_response_parser.py -q`

Expected: FAIL，模块不存在。

- [ ] **Step 3：实现稳定接口**

```python
class PromptRegistry:
    def render(self, task_key: str, **variables: object) -> tuple[str, str]: ...


class ResponseParser:
    @staticmethod
    def extract_content(payload: dict) -> str: ...
    @staticmethod
    def parse_json(text: str, schema: type[BaseModel] | None = None) -> dict | list: ...
```

`PromptRegistry` 同时校验 cfg 中声明的 `variables` 和模板实际占位符集合；`ResponseParser` 复用并收敛 `apps.common.utils.repair_json_string` 的能力。

- [ ] **Step 4：把全部现有 Python 提示词等价迁入 cfg**

从 `apps/common/ai_prompts.py`、`apps/study/ai_helper.py`、`apps/study/photo_views.py`、`apps/courses/prompts.py`、`apps/parser/prompts/*.py` 逐项迁入，保持原输出字段和教学约束不变；此步骤暂不删除源文件。

- [ ] **Step 5：运行测试确认通过**

Run: `python -m pytest apps/common/ai/tests/test_prompt_registry.py apps/common/ai/tests/test_response_parser.py tests/test_ai_pipeline.py -q`

Expected: PASS。

- [ ] **Step 6：提交提示词与解析器**

```powershell
git add -- config/ai_config.cfg apps/common/ai/prompt_registry.py apps/common/ai/response_parser.py apps/common/ai/schemas.py apps/common/ai/tests
git commit -m "feat: centralize AI prompts and response parsing"
```

---

## Task 4：实现统一 AIClient、重试分类和脱敏日志

**Files:**

- Create: `apps/common/ai/client.py`
- Create: `apps/common/ai/types.py`
- Create: `apps/common/ai/redaction.py`
- Create: `apps/common/ai/tests/test_client.py`

- [ ] **Step 1：写 payload、重试和脱敏失败测试**

用 `unittest.mock.patch("httpx.Client.post")` 覆盖：

- 文本消息与多模态 `image_url` 消息格式。
- `response_format=json_object` 的任务配置。
- 429、500、ReadTimeout 按 cfg 重试并调用注入的 sleeper。
- 401/403 只请求一次。
- choices 为空抛 `AIResponseError`。
- 日志和异常中不存在 `test-secret` 与 `data:image/...;base64,` 的完整内容。

- [ ] **Step 2：运行测试确认失败**

Run: `python -m pytest apps/common/ai/tests/test_client.py -q`

Expected: FAIL，`AIClient` 尚不存在。

- [ ] **Step 3：实现客户端和调用结果类型**

```python
@dataclass(frozen=True)
class AIResult:
    content: str
    provider: str
    model: str
    latency_ms: int
    raw_response: dict


class AIClient:
    def complete(self, task_key: str, *, system: str, user: str,
                 images: Sequence[str] = (), trace_id: str | None = None) -> AIResult: ...
```

客户端从 `AIConfig` 获取 provider、URL、Key、模型和参数；仅 429、5xx、连接/读取超时重试；构造可注入 transport/sleeper 的实例以确保测试不真实等待。

- [ ] **Step 4：运行客户端测试**

Run: `python -m pytest apps/common/ai/tests/test_client.py -q`

Expected: PASS，且测试总时长不包含真实退避等待。

- [ ] **Step 5：提交统一客户端**

```powershell
git add -- apps/common/ai/client.py apps/common/ai/types.py apps/common/ai/redaction.py apps/common/ai/tests/test_client.py
git commit -m "feat: add unified AI provider client"
```

---

## Task 5：实现题目探查、A/B/C 答案与通用校验组件

**Files:**

- Create: `apps/common/ai/components/__init__.py`
- Create: `apps/common/ai/components/base.py`
- Create: `apps/common/ai/components/question_probe.py`
- Create: `apps/common/ai/components/mode_answers.py`
- Create: `apps/common/ai/components/result_verifier.py`
- Create: `apps/common/ai/tests/test_question_components.py`
- Modify: `apps/common/ai_service.py`
- Modify: `tests/test_ai_pipeline.py`
- Modify: `apps/review/tests.py`

- [ ] **Step 1：写组件路由与兼容契约失败测试**

```python
def test_probe_uses_flash_and_returns_taxonomy(ai_client):
    result = QuestionProbeComponent(ai_client).run(QuestionInput(stem="..."))
    ai_client.complete.assert_called_once()
    assert ai_client.complete.call_args.args[0] == "question_probe"
    assert set(result) >= {"subject", "question_type", "grade", "semester",
                           "chapter", "difficulty", "knowledge_points"}


def test_legacy_service_keeps_mode_a_shape(component_factory, question):
    result = AIReviewService(component_factory=component_factory).generate_answer_a(question)
    assert set(result) >= {"mode", "steps", "final_answer", "summary"}
```

分别覆盖 Mode B 的 `questions/options/correct_answer/explanation`、Mode C 的开放问题字段、通用校验器和多图输入。

- [ ] **Step 2：运行定向测试确认失败**

Run: `python -m pytest apps/common/ai/tests/test_question_components.py tests/test_ai_pipeline.py apps/review/tests.py -q`

Expected: 新组件测试 FAIL；旧测试保持现状结果。

- [ ] **Step 3：实现 DTO 和业务组件**

```python
@dataclass(frozen=True)
class QuestionInput:
    stem: str
    options: dict | list | None = None
    answer: str = ""
    solution: str = ""
    image_urls: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)
```

每个组件固定使用 task key，调用 `PromptRegistry -> AIClient -> ResponseParser`，不访问数据库。

- [ ] **Step 4：将 AIReviewService 改为薄兼容适配器**

保留以下公共方法签名及输出：`analyze_knowledge`、`generate_answer_a/b/c`、`probe_and_norm`、`vision_extraction`、`solve_mode_a/b/c`、`verify_result`、`analyze_knowledge_points`、`process_question_full(_v2)`、`save_results_to_question`。删除其内部 HTTP 逻辑，但暂不删除模块路径。

- [ ] **Step 5：运行组件及 review 回归**

Run: `python -m pytest apps/common/ai/tests/test_question_components.py tests/test_ai_pipeline.py apps/review/tests.py -q`

Expected: PASS，原有 review mock 测试仍可使用既有入口。

- [ ] **Step 6：提交核心题目组件**

```powershell
git add -- apps/common/ai/components apps/common/ai/tests/test_question_components.py apps/common/ai_service.py tests/test_ai_pipeline.py apps/review/tests.py
git commit -m "refactor: route question AI flows through shared components"
```

---

## Task 6：迁移 common/review 调用方和持久化链路

**Files:**

- Modify: `apps/common/batch_tasks.py`
- Modify: `apps/common/management/commands/generate_ai_guidance.py`
- Modify: `apps/review/tasks.py`
- Modify: `apps/review/views.py`
- Modify: `apps/review/services/ai_review_service.py`
- Modify: `apps/review/tests.py`
- Create: `apps/common/ai/tests/test_review_compatibility.py`

- [ ] **Step 1：写兼容调用与数据库映射失败测试**

测试批处理、单题 review、管理命令均通过适配器调用组件；校验 `ai_answer_a/b/c`、知识点、`ai_process_status` 和错误状态字段写入结构不变。

- [ ] **Step 2：运行测试确认新增断言失败**

Run: `python -m pytest apps/common/ai/tests/test_review_compatibility.py apps/review/tests.py -q`

Expected: FAIL，调用仍指向旧内部实现或缺少注入点。

- [ ] **Step 3：逐入口替换依赖**

让 view/task/command 只调用兼容 facade 或公共组件工厂；保留原 Celery task 名、参数、缓存 key、进度百分比和返回字典。

- [ ] **Step 4：运行定向测试**

Run: `python -m pytest apps/common/ai/tests/test_review_compatibility.py apps/review/tests.py tests/integration/test_review.py -q`

Expected: PASS。

- [ ] **Step 5：提交 review/common 迁移**

```powershell
git add -- apps/common/batch_tasks.py apps/common/management/commands/generate_ai_guidance.py apps/review apps/common/ai/tests/test_review_compatibility.py
git commit -m "refactor: migrate review AI workflows to shared components"
```

---

## Task 7：迁移学生和教师引导 AI

**Files:**

- Create: `apps/common/ai/components/guidance.py`
- Create: `apps/common/ai/tests/test_guidance_component.py`
- Modify: `apps/study/ai_helper.py`
- Modify: `apps/study/guidance_views.py`
- Modify: `apps/missions/views.py`
- Create: `apps/study/tests/__init__.py`
- Create: `apps/study/tests/test_guidance_ai.py`
- Create: `apps/missions/tests/__init__.py`
- Create: `apps/missions/tests/test_guidance_ai.py`

- [ ] **Step 1：写引导生成、评价及降级契约失败测试**

覆盖：C 模式预生成内容为空时生成 3-5 步；学生回复评价；教师引导评价；Key 缺失或供应商异常时仍返回现有安全兜底文案/空字典；所有调用 task key 使用 `qwen3.7-flash` 路由。

- [ ] **Step 2：运行测试确认失败**

Run: `python -m pytest apps/common/ai/tests/test_guidance_component.py apps/study/tests/test_guidance_ai.py apps/missions/tests/test_guidance_ai.py -q`

Expected: FAIL，组件不存在且现有代码仍直接请求 Qwen。

- [ ] **Step 3：实现 GuidanceComponent 和薄兼容包装器**

```python
class GuidanceComponent:
    def generate(self, question: QuestionInput) -> dict: ...
    def evaluate_student_reply(self, context: GuidanceContext) -> str: ...
    def evaluate_teacher_reply(self, context: GuidanceContext) -> dict: ...
```

`apps/study/ai_helper.py` 仅保留旧函数名的转发包装器；从 `missions/views.py` 删除 `_call_qwen` 并调用组件。

- [ ] **Step 4：运行定向与接口回归**

Run: `python -m pytest apps/common/ai/tests/test_guidance_component.py apps/study/tests/test_guidance_ai.py apps/missions/tests/test_guidance_ai.py tests/integration/test_student.py tests/integration/test_missions.py -q`

Expected: PASS。

- [ ] **Step 5：提交引导迁移**

```powershell
git add -- apps/common/ai/components/guidance.py apps/common/ai/tests/test_guidance_component.py apps/study/ai_helper.py apps/study/guidance_views.py apps/study/tests apps/missions/views.py apps/missions/tests
git commit -m "refactor: unify student and teacher AI guidance"
```

---

## Task 8：迁移 parser 与拍照识题视觉 AI

**Files:**

- Create: `apps/common/ai/components/vision_parser.py`
- Create: `apps/common/ai/image_codec.py`
- Create: `apps/common/ai/tests/test_vision_parser.py`
- Modify: `apps/parser/services/position_service.py`
- Modify: `apps/parser/services/question_parse_service.py`
- Modify: `apps/parser/tasks.py`
- Modify: `apps/parser/tests.py`
- Modify: `apps/study/photo_views.py`
- Create: `apps/study/tests/__init__.py`（若 Task 7 尚未创建）
- Create: `apps/study/tests/test_photo_ai.py`

- [ ] **Step 1：写视觉 payload、解析结果和兼容持久化失败测试**

覆盖本地图片压缩/base64、OSS URL、页面定位返回 `raw_response/response_json/latency_ms`、逐题解析、拍照识题 JSON、parser 任务的 `model_name` 升级为 `qwen3.7-plus-position`，以及图片内容不写日志。

- [ ] **Step 2：运行测试确认失败**

Run: `python -m pytest apps/common/ai/tests/test_vision_parser.py apps/parser/tests.py apps/study/tests/test_photo_ai.py -q`

Expected: FAIL，新组件不存在。

- [ ] **Step 3：实现 VisionParserComponent**

```python
class VisionParserComponent:
    def detect_positions(self, image_path: str) -> AIResult: ...
    def parse_page(self, image_path: str) -> AIResult: ...
    def parse_question(self, images: Sequence[str], context: dict) -> dict: ...
    def recognize_photo(self, images: Sequence[str]) -> dict: ...
    def extract_facts(self, images: Sequence[str], stem: str) -> dict: ...
```

位置探查 task 路由 `qwen3.7-plus`；页面/逐题/拍照/图像事实 task 路由 `qwen3-vl-plus`。

- [ ] **Step 4：迁移 parser 和 photo 调用方**

`position_service.py`、`question_parse_service.py`、`parser/tasks.py` 和 `photo_views.py` 改为组件调用。保留 Celery task 名、进度节点、`AIParseResult` 字段以及 API envelope。

- [ ] **Step 5：运行定向回归**

Run: `python -m pytest apps/common/ai/tests/test_vision_parser.py apps/parser/tests.py apps/study/tests/test_photo_ai.py tests/integration/test_papers.py -q`

Expected: PASS。

- [ ] **Step 6：提交视觉迁移**

```powershell
git add -- apps/common/ai/components/vision_parser.py apps/common/ai/image_codec.py apps/common/ai/tests/test_vision_parser.py apps/parser/services/position_service.py apps/parser/services/question_parse_service.py apps/parser/tasks.py apps/parser/tests.py apps/study/photo_views.py apps/study/tests/test_photo_ai.py
git commit -m "refactor: route parser and photo AI through vision component"
```

---

## Task 9：迁移课程变式题并保留 DeepSeek 二次校验

**Files:**

- Create: `apps/common/ai/components/variant_generator.py`
- Create: `apps/common/ai/tests/test_variant_components.py`
- Modify: `apps/common/ai/components/result_verifier.py`
- Modify: `apps/courses/ai_service.py`
- Modify: `apps/courses/tasks.py`
- Modify: `apps/courses/views.py`
- Create: `apps/courses/tests/test_variant_ai.py`

- [ ] **Step 1：写双提供商调用顺序和失败策略测试**

```python
def test_variant_generation_uses_qwen_then_deepseek(factory):
    result = factory.variant_generator().generate(question_input, "same_knowledge")
    assert factory.client.task_keys == ["variant_generate", "variant_verify_deepseek"]
    assert result["verification"]["provider"] == "deepseek"
```

覆盖 DeepSeek 校验不通过后的现有一次重试、DeepSeek Key 缺失时的现有跳过行为、Celery retry、任务状态和确认保存字段。

- [ ] **Step 2：运行测试确认失败**

Run: `python -m pytest apps/common/ai/tests/test_variant_components.py apps/courses/tests/test_variant_ai.py -q`

Expected: FAIL，新组件不存在。

- [ ] **Step 3：实现变式生成与 DeepSeek 校验组件**

```python
class VariantGeneratorComponent:
    def generate(self, question: QuestionInput, variant_mode: str) -> dict: ...


class ResultVerifierComponent:
    def verify(self, task_key: str, original: dict, candidate: dict) -> dict: ...
```

生成固定路由 `variant_generate/qwen3.7-plus`；二次校验固定路由 `variant_verify_deepseek/deepseek`，不得降级成 Qwen 校验而隐藏 DeepSeek 故障。

- [ ] **Step 4：将 courses 任务和视图改为组件调用**

保持 `generate_variant_task`、`batch_generate_variants_task` 的名称/参数、进度/错误状态和 `VariantTask` 持久化结构不变。`apps/courses/ai_service.py` 暂仅留旧模块级函数的薄适配器。

- [ ] **Step 5：运行课程回归**

Run: `python -m pytest apps/common/ai/tests/test_variant_components.py apps/courses/tests -q`

Expected: PASS，断言 Qwen 生成和 DeepSeek 校验均被调用。

- [ ] **Step 6：提交课程迁移**

```powershell
git add -- apps/common/ai/components/variant_generator.py apps/common/ai/components/result_verifier.py apps/common/ai/tests/test_variant_components.py apps/courses/ai_service.py apps/courses/tasks.py apps/courses/views.py apps/courses/tests/test_variant_ai.py
git commit -m "refactor: preserve DeepSeek verification in shared variant flow"
```

---

## Task 10：删除旧 AI 实现并建立架构禁用扫描

**Files:**

- Delete: `apps/common/ai_prompts.py`
- Delete: `apps/common/ai_prompts.py.bak`
- Delete: `apps/courses/prompts.py`
- Delete: `apps/parser/services/qwen_text_service.py`
- Delete: `apps/parser/services/qwen_vl_service.py`
- Modify or Delete: `apps/study/ai_helper.py`
- Modify or Delete: `apps/courses/ai_service.py`
- Modify: `tests/test_ai_architecture_inventory.py`
- Modify: `docs/ai_process(0801）.md`

- [ ] **Step 1：扩展架构测试，使旧实现仍存在时失败**

```python
FORBIDDEN_ACTIVE_PATTERNS = (
    "qwen3.6-flash", "qwen3.6-plus",
    "dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
)


def test_only_shared_client_calls_httpx_post():
    offenders = scan_python_sources("httpx.Client") - {"apps/common/ai/client.py"}
    assert offenders == set()


def test_only_config_layer_reads_ai_secrets():
    offenders = scan_python_sources("QWEN_API_KEY", "DEEPSEEK_API_KEY")
    assert offenders <= {"apps/common/ai/config.py"}
```

扫描排除 migrations、测试 fixture、历史设计文档和 `docs/ai_process` 的“迁移前”说明，但不排除活跃 Python 和 `config/ai_config.cfg`。

- [ ] **Step 2：运行测试确认旧代码触发失败**

Run: `python -m pytest tests/test_ai_architecture_inventory.py -q`

Expected: FAIL，并列出旧 HTTP 客户端、内嵌模型名和提示词文件。

- [ ] **Step 3：删除旧实现并修复所有 import**

只有在 Tasks 5-9 的调用方测试全部通过后执行删除。若旧模块路径仍被外部/测试导入，只留下转发到公共组件的薄适配器；其中不得包含 prompt、URL、Key、`httpx.Client` 或模型路由。

- [ ] **Step 4：更新最终处理文档**

在 `docs/ai_process(0801）.md` 给每个入口标注“已迁移”，列出实际 task key、模型、公共组件、错误策略和持久化位置，并明确 DeepSeek 校验仍启用。

- [ ] **Step 5：运行禁用扫描与相关全量测试**

Run: `python -m pytest tests/test_ai_architecture_inventory.py apps/common/ai/tests tests/test_ai_pipeline.py apps/review/tests.py apps/parser/tests.py apps/courses/tests apps/study/tests apps/missions/tests -q`

Expected: PASS。

Run: `rg -n "qwen3\\.6-(flash|plus)|httpx\\.Client|chat/completions|QWEN_API_KEY|DEEPSEEK_API_KEY" apps config/ai_config.cfg`

Expected: 3.6 无匹配；`httpx.Client`/`chat/completions`/Key 只出现在允许的公共客户端或配置层位置。

- [ ] **Step 6：提交旧代码清理**

```powershell
git add -u -- apps/common/ai_prompts.py apps/common/ai_prompts.py.bak apps/courses/prompts.py apps/parser/services/qwen_text_service.py apps/parser/services/qwen_vl_service.py apps/study/ai_helper.py apps/courses/ai_service.py
git add -- tests/test_ai_architecture_inventory.py "docs/ai_process(0801）.md"
git commit -m "refactor: remove obsolete direct AI integrations"
```

---

## Task 11：增加并执行真实 Qwen/DeepSeek 最小冒烟测试

**Files:**

- Create: `apps/common/management/commands/ai_smoke_test.py`
- Create: `apps/common/ai/tests/test_smoke_command.py`
- Modify: `docs/ai_process(0801）.md`

- [ ] **Step 1：写命令行为测试**

mock `AIClient`，验证默认不执行真实网络、`--provider qwen` 只调用 `question_probe`、`--provider deepseek` 只调用 `variant_verify_deepseek`、输出仅含 provider/model/status/latency/schema，不含 Key 或完整响应。

- [ ] **Step 2：运行测试确认失败**

Run: `python -m pytest apps/common/ai/tests/test_smoke_command.py -q`

Expected: FAIL，命令不存在。

- [ ] **Step 3：实现显式真实调用命令**

```text
python manage.py ai_smoke_test --provider qwen --live
python manage.py ai_smoke_test --provider deepseek --live
```

未提供 `--live` 时拒绝网络调用。Qwen 使用最小中文分类输入；DeepSeek 使用最小原题/候选题校验输入。命令只输出脱敏摘要，并以非零退出码区分配置、网络、HTTP、Schema 错误。

- [ ] **Step 4：运行命令单元测试**

Run: `python -m pytest apps/common/ai/tests/test_smoke_command.py -q`

Expected: PASS。

- [ ] **Step 5：执行用户已批准的两次真实调用**

Run: `python manage.py ai_smoke_test --provider qwen --live`

Expected: `provider=qwen status=ok schema=valid`，不显示 Key。

Run: `python manage.py ai_smoke_test --provider deepseek --live`

Expected: `provider=deepseek status=ok schema=valid`，不显示 Key。

若外网/供应商失败：保存退出分类、HTTP 状态和脱敏错误；不得把它表述成单元测试失败，也不得反复消费真实调用额度。

- [ ] **Step 6：记录冒烟结果并提交工具**

```powershell
git add -- apps/common/management/commands/ai_smoke_test.py apps/common/ai/tests/test_smoke_command.py "docs/ai_process(0801）.md"
git commit -m "test: add opt-in AI provider smoke checks"
```

---

## Task 12：最终验证、差异审查与交付

**Files:**

- Verify only; only fix files already listed above if a verification failure requires it.

- [ ] **Step 1：执行 Django 配置检查**

Run: `python manage.py check`

Expected: `System check identified no issues`。

- [ ] **Step 2：执行 AI/业务定向套件**

Run: `python -m pytest apps/common/ai/tests tests/test_ai_pipeline.py tests/test_ai_architecture_inventory.py apps/review/tests.py apps/parser/tests.py apps/courses/tests apps/study/tests apps/missions/tests -q`

Expected: 全部 PASS。

- [ ] **Step 3：执行全部非 E2E 测试**

Run: `python -m pytest -m "not e2e" -q`

Expected: 全部 PASS；若存在与本任务无关的基线失败，记录完整测试名并用修改前基线复核，不能隐瞒或误称全部通过。

- [ ] **Step 4：执行最终静态约束扫描**

Run: `rg -n "qwen3\\.6-(flash|plus)" apps config`

Expected: 无匹配。

Run: `rg -n "httpx\\.Client|chat/completions|QWEN_API_KEY|DEEPSEEK_API_KEY" apps`

Expected: 仅公共配置/客户端及明确的测试断言中出现。

- [ ] **Step 5：审查实际改动范围和敏感文件**

Run: `git status --short`

Expected: 除用户原有 `.env`、dump、media、`.superpowers`、`docs/improve.md` 等未提交项外，只含本计划文件；所有任务代码已经按小提交提交。

Run: `git diff --name-only HEAD~12..HEAD`

Expected: 所有路径均位于 `front/` 仓库内，不包含 `.env`、dump、media 或临时目录。

- [ ] **Step 6：人工审查兼容性与密钥泄露**

逐项确认 API URL/参数/envelope、Celery 名称、数据库字段映射未变；使用 `git show --stat` 和 staged diff 确认无 Key 明文。必要修复后重跑对应测试。

- [ ] **Step 7：交付证据**

最终报告分别列出：静态约束、模拟测试、Django check、全量非 E2E、Qwen 真实冒烟、DeepSeek 真实冒烟的结果；不得用“代码存在”代替“真实调用成功”。
