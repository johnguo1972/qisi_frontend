# AI 公共组件重构设计

## 1. 目标

在不改变现有前端 API、Celery 任务名、数据库字段及返回 JSON 契约的前提下，将 `front/` 内所有大模型调用收敛为分层公共 AI 内核，并完成以下事项：

- 在 `docs/ai_process(0801）.md` 记录全部活跃 AI 调用的入口、处理步骤、模型、提示词、输入输出、持久化和异常策略。
- 建立题目探查、A/B/C 模式答案、视觉解析、学生/教师引导、变式题生成和结果校验等公共业务组件。
- 将 `qwen3.6-flash` 统一替换为 `qwen3.7-flash`，将 `qwen3.6-plus` 统一替换为 `qwen3.7-plus`。
- 保留 `qwen3-vl-plus` 处理视觉解析；保留 DeepSeek 作为课程变式题的二次校验模型。
- 模型 URL、API Key 和 OSS 等连接信息只保存在 `.env`；模型映射、调用参数和提示词只保存在 `config/ai_config.cfg`。
- 所有调用方切换并通过模拟测试与真实模型冒烟测试后，删除已作废的直连客户端和 Python 内嵌提示词。

## 2. 现状与问题

当前活跃 AI 调用分散在以下区域：

- `apps/common/ai_service.py`：题目探查、知识点分析、A/B/C 答案、读图、结果校验及持久化。
- `apps/study/ai_helper.py`、`apps/study/guidance_views.py`：学生 C 模式实时引导与回答评价。
- `apps/missions/views.py`：教师引导回答评价，包含独立 `_call_qwen`。
- `apps/study/photo_views.py`：拍照识题，包含独立视觉模型 HTTP 调用和内嵌提示词。
- `apps/courses/ai_service.py`、`apps/courses/prompts.py`、`apps/courses/tasks.py`：变式题生成与 DeepSeek 校验。
- `apps/parser/services/qwen_text_service.py`、`qwen_vl_service.py`、`question_parse_service.py`：试卷题目定位和逐题视觉解析。

主要问题：

- 至少六套代码直接请求 OpenAI 兼容的 `chat/completions`。
- URL、API Key 读取、重试、超时、日志和 JSON 解析策略不一致。
- 提示词分散在多个 Python 文件，难以统一版本管理和审查。
- 活跃代码仍大量硬编码 `qwen3.6-flash/plus`，部分环境变量没有被 Django settings 实际加载。
- `AIReviewService` 同时承担传输、模型路由、提示词、业务编排和持久化，职责过重。

## 3. 总体架构

新增 `apps/common/ai/` 包，分成四层：

1. **配置层**：启动时加载并校验 `.env` 与 `config/ai_config.cfg`。
2. **公共内核层**：统一模型客户端、提示词注册表、响应解析器和异常类型。
3. **业务组件层**：每个组件只负责一种 AI 业务能力。
4. **兼容适配层**：保留现有调用签名和输出结构，将调用转发到新组件。

调用方向固定为：

`现有 View/Task/Command -> 兼容适配 -> 业务组件 -> PromptRegistry -> AIClient -> 模型 -> ResponseParser -> 兼容输出/持久化`

禁止业务组件直接读取 API Key、直接拼接提供商 URL 或自行创建 `httpx.Client`。

## 4. 配置设计

### 4.1 `.env`

仅保存连接和敏感信息：

- `QWEN_API_KEY`
- `QWEN_API_HOST`
- `QWEN_OPENAI_BASE_URL`
- `QWEN_API_URL`
- `DASHSCOPE_API_URL`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_API_URL`
- OSS 相关环境变量

文档、日志和测试输出不得包含 Key 明文。

### 4.2 `config/ai_config.cfg`

UTF-8 编码，保存：

- 提供商与任务的模型映射。
- `temperature`、`max_tokens`、`timeout_seconds`、`retry_count`、退避间隔。
- 全部 system/user 提示词。
- 每项提示词允许的占位变量清单。

配置在 Django/Celery 启动时加载一次。缺少必需 section、模型映射、提示词或占位变量时抛出 `AIConfigError`，阻止服务带错误配置启动。运行中不热加载，修改后必须重启。

## 5. 模型路由

- `qwen3.7-flash`：题目探查、学科/题型/年级学期/章节/难度/知识点分析、轻量结果校验、学生和教师实时评价。
- `qwen3.7-plus`：A/B/C 模式答案、复杂推理、题目位置探查、课程变式题生成。
- `qwen3-vl-plus`：页面视觉解析、逐题视觉解析、拍照识题和图像事实抽取。
- DeepSeek：仅用于课程变式题二次校验。

活跃代码、运行配置和默认回退值中不得再出现 `qwen3.6-flash` 或 `qwen3.6-plus`。历史说明文档可提及迁移前模型，但必须标注为旧值。

## 6. 公共内核

### 6.1 `AIConfig`

- 读取环境变量和 cfg。
- 提供 `get_task_config(task_key)` 与 `get_provider_config(provider)`。
- 启动时执行必需项、类型、范围和占位符校验。

### 6.2 `PromptRegistry`

- 以稳定 task key 读取 system/user 提示词。
- 使用显式变量渲染，缺少变量立即失败，不静默保留占位符。
- 不允许业务代码内嵌完整提示词。

### 6.3 `AIClient`

- 支持文本和 OpenAI 兼容多模态消息。
- 统一超时、重试、指数退避、状态码分类、trace ID 和耗时记录。
- 429、5xx、读取超时可重试；401/403、配置错误和请求 Schema 错误不可重试。
- 日志不记录 API Key、完整 base64、手机号或其他个人信息。

### 6.4 `ResponseParser`

- 提取 assistant content。
- 去除 Markdown fence，修复可恢复的 JSON 包裹、尾逗号和截断。
- 按组件 Schema 校验；不可恢复响应抛出统一 `AIResponseError`。
- 审计日志只保留必要且截断后的原始响应。

## 7. 业务组件

- `QuestionProbeComponent`：题型、学科、年级学期、章节、难度、知识点、OCR 规范化和路由建议。
- `ModeAAnswerComponent`：直接解答、3-5 个步骤、最终答案、总结和缺失条件。
- `ModeBAnswerComponent`：3-4 个递进选择题、A-D 选项、正确项、解析、最终答案和总结。
- `ModeCAnswerComponent`：开放式引导题、参考答案、评分点、追问提示、最终答案和总结。
- `VisionParserComponent`：页面定位、逐题解析、拍照识题和图像事实抽取。
- `GuidanceComponent`：预生成引导内容缺失时的实时生成，以及学生/教师回复评价。
- `VariantGeneratorComponent`：变式题生成并保持原有任务和持久化契约。
- `ResultVerifierComponent`：Qwen 通用校验；变式题使用 DeepSeek 二次校验。

组件输入使用明确 DTO，输出为经过 Schema 校验的字典。组件不直接写数据库；现有服务或任务负责兼容映射和持久化。

## 8. 兼容要求

- UniApp 请求地址、参数和响应 envelope 不变。
- 现有 Celery task 名称、参数和状态值不变。
- `ExamQuestion` 的 `ai_answer_a`、`ai_answer_b`、`ai_answer_c`、知识点和处理状态字段写入格式不变。
- 现有 A/B/C 页面依赖的 `steps`、`questions`、`final_answer`、`summary` 等字段保持兼容。
- 现有 parser/review/course/study/mission 入口只替换内部依赖。

## 9. 迁移与删除顺序

1. 生成 `docs/ai_process(0801）.md` 作为现状基线。
2. 新增配置层、公共内核和业务组件，不立即删除旧实现。
3. 使用模拟响应建立组件和兼容契约测试。
4. 按 `review/common -> study/missions -> parser/photo -> courses/variant` 逐域切换。
5. 每个域切换后运行定向测试。
6. 所有调用方切换后运行 Django check、完整相关测试、禁用字符串扫描及 Qwen/DeepSeek 真实冒烟。
7. 删除旧 HTTP 实现与内嵌提示词。
8. 删除后再次运行完整测试与真实冒烟，确认没有隐藏依赖。

待删除或清空的旧实现包括：

- `apps/common/ai_prompts.py` 中的内嵌提示词。
- `apps/study/ai_helper.py` 的独立 HTTP 调用。
- `apps/missions/views.py::_call_qwen`。
- `apps/study/photo_views.py::_call_vision_api` 的直连逻辑。
- `apps/courses/ai_service.py`、`apps/courses/prompts.py` 的重复客户端和提示词。
- `apps/parser/services/qwen_text_service.py`、`qwen_vl_service.py` 的重复客户端。

需要保留旧模块路径时，只允许留下无业务逻辑的薄适配器；不得保留第二套请求、模型路由或提示词。

## 10. 测试策略

### 10.1 配置测试

- UTF-8 cfg 加载。
- 必需 section、类型、模型和环境变量校验。
- 提示词占位符完整性与非法变量检测。
- URL 与 Key 不进入日志和异常文本。

### 10.2 公共内核测试

- 文本和多模态 payload。
- 超时、429、5xx 重试与退避。
- 401/403 和配置错误立即失败。
- JSON 提取、修复、不可恢复响应和 Schema 错误。

### 10.3 组件与兼容契约测试

- Probe、A、B、C、Vision、Guidance、Variant、Verifier 分别使用 mock 模型响应。
- 校验旧函数签名、API JSON、Celery 结果和数据库字段映射。
- 验证变式题生成使用 Qwen，二次校验使用 DeepSeek。

### 10.4 真实冒烟测试

用户已授权使用 `.env` 中的真实 Key 执行最小请求：

- 一次 Qwen 文本或结构化 JSON 调用。
- 一次 DeepSeek 变式题校验调用。

真实测试记录模型、HTTP 状态、耗时和响应 Schema，不输出 Key 或完整敏感内容。外部网络或供应商失败必须与代码测试失败分开报告。

## 11. 完成标准

- `docs/ai_process(0801）.md` 完整记录所有活跃 AI 调用链和迁移结果。
- 所有活跃调用均经过公共 AI 内核。
- 模型 URL 只从 `.env` 读取，提示词只从 `ai_config.cfg` 读取。
- 除配置层和公共客户端外，无代码直接读取 AI Key 或请求 `chat/completions`。
- 活跃代码与运行配置中不存在 Qwen 3.6 模型值。
- 兼容契约、Django check、相关测试套件和静态禁用扫描通过。
- Qwen 与 DeepSeek 最小真实冒烟测试成功，或明确记录可复现的外部阻塞证据。
- 旧 AI 请求实现和内嵌提示词已删除，删除后完整验证再次通过。

## 12. 范围约束

- 所有文件修改严格限定在 `./front`。
- 不修改其他目录中的代码、配置或文档。
- 不提交 `.env`、dump、媒体文件、构建产物或其他无关未提交文件。
