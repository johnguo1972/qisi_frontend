# AI 大模型处理流程与公共组件清单（2026-08-01）

## 1. 文档口径

本文记录 `front/` 当前启用的 AI 调用链。所有列出的活跃入口均已迁移到公共 AI 内核；旧 URL、密钥读取、Python 内嵌提示词和重复 HTTP 客户端已从业务代码移除。

需要区分以下验证层级：

- “已迁移”表示调用方已经通过公共组件进入 `PromptRegistry -> AIClient -> ResponseParser/Schema`。
- Task10 的测试使用模拟模型响应，验证组件、接口、任务和持久化契约，不代表外部模型真实可用。
- Qwen 与 DeepSeek 的真实最小调用由 Task11 的显式 `--live` 冒烟命令执行；在该命令产生证据前，本文不宣称真实调用成功。

## 2. 统一架构与配置职责

固定调用方向为：

`View/Task/Command -> 兼容适配或公共组件工厂 -> 业务组件 -> PromptRegistry -> AIClient -> 提供商 -> ResponseParser/严格 Schema -> 兼容输出/持久化`

| 配置位置 | 只允许保存的内容 | 禁止内容 |
| --- | --- | --- |
| `.env` | Qwen/DeepSeek URL、API Key 等连接信息 | 提示词、任务模型路由 |
| `config/ai_config.cfg` | provider/task 映射、模型、温度、token、300 秒超时、重试、全部提示词 | 密钥明文、业务持久化逻辑 |
| `apps/common/ai/client.py` | 唯一 AI HTTP 客户端、重试分类、脱敏日志 | 业务提示词、数据库访问 |
| `apps/common/ai/components/` | 题目、引导、视觉、变式与校验业务组件 | URL、Key、直接 HTTP、数据库写入 |

所有 Qwen 与 DeepSeek task 的 `timeout_seconds` 均为 `300`。可重试范围由 `AIClient` 统一控制：连接/读取超时、429 和 5xx 按 cfg 退避；401/403、配置错误、提示词错误和 Schema 错误不伪造成功。

## 3. 当前 task key、模型与公共组件

| task key | provider | 模型 | 公共组件/方法 | 响应处理 |
| --- | --- | --- | --- | --- |
| `question_probe` | Qwen | `qwen3.7-flash` | `QuestionProbeComponent.run` | `QuestionProbeResponse` 严格分类 Schema |
| `knowledge_analysis` | Qwen | `qwen3.7-flash` | `KnowledgeAnalysisComponent.run` | `KnowledgeAnalysisResponse` |
| `mode_a_answer` | Qwen | `qwen3.7-plus` | `ModeAAnswerComponent.run` | A 模式步骤/答案严格 Schema |
| `mode_b_answer` | Qwen | `qwen3.7-plus` | `ModeBAnswerComponent.run` | B 模式问题、A-D 选项和答案严格 Schema |
| `mode_c_answer` | Qwen | `qwen3.7-plus` | `ModeCAnswerComponent.run` | C 模式开放问题和追问严格 Schema |
| `result_verify` | Qwen | `qwen3.7-flash` | `ResultVerifierComponent.run` | 通用结果校验 Schema |
| `vision_fact_extract` | Qwen | `qwen3-vl-plus` | `VisionParserComponent.extract_facts` | 图像事实对象解析 |
| `vision_page_parse` | Qwen | `qwen3-vl-plus` | `VisionParserComponent.parse_page` | 整页题目对象解析与审计字段 |
| `vision_question_parse` | Qwen | `qwen3-vl-plus` | `VisionParserComponent.parse_question` | 逐题对象解析与审计字段 |
| `vision_position_detect` | Qwen | `qwen3.7-plus` | `VisionParserComponent.detect_positions` | 题目位置对象解析与审计字段 |
| `guidance_generate` | Qwen | `qwen3.7-flash` | `GuidanceComponent.generate` | 3-5 步引导严格 Schema |
| `guidance_evaluate` | Qwen | `qwen3.7-flash` | `GuidanceComponent.evaluate_student_reply` | 非空评价文本 |
| `teacher_guidance_evaluate` | Qwen | `qwen3.7-flash` | `GuidanceComponent.evaluate_teacher_reply` | 教师评价对象 Schema |
| `variant_generate` | Qwen | `qwen3.7-plus` | `VariantGeneratorComponent.generate` | 变式题严格 Schema 与原始审计字段 |
| `variant_verify_deepseek` | DeepSeek | `deepseek-v4-pro` | `ResultVerifierComponent.verify` | DeepSeek 校验严格 Schema |
| `photo_recognize` | Qwen | `qwen3-vl-plus` | `VisionParserComponent.recognize_photo` | 拍照题目 JSON 对象 |
| `course_material_recognize` | Qwen | `qwen3-vl-plus` | `VisionParserComponent.recognize_course_material` | 专用成功/未识别联合严格 Schema |

## 4. 活跃入口详细处理流程

### 4.1 common/review：题目探查、知识分析和 A/B/C 答案（已迁移）

- 入口：`apps/common/batch_tasks.py`、`apps/common/management/commands/generate_ai_guidance.py`、`apps/review/tasks.py`、`apps/review/views.py`、`apps/review/services/ai_review_service.py`。
- 兼容外壳：`apps/common/ai_service.py:AIReviewService` 保留原公开方法和 mock 注入点，不再拥有 provider HTTP、URL、Key 或提示词。
- 输入：题干、已有答案/解析、选项、题图、知识点和题目元数据，统一转换为 `QuestionInput`。
- 处理链：`question_probe` -> 可选 `vision_fact_extract` -> `knowledge_analysis` -> `mode_a_answer`/`mode_b_answer`/`mode_c_answer` -> `result_verify`。
- 错误策略：公共客户端执行 HTTP 分类重试；组件拒绝不可恢复 JSON/Schema；完整流程保留 partial/error 状态，单模式失败不伪造其它模式成功。
- 持久化：兼容服务写回 `ExamQuestion.ai_probe_result`、`ai_vision_extract`、`ai_knowledge_enrichment`、`ai_answer_a/b/c`、`ai_verifier_result`、`ai_processing_status`、`ai_processed_at`；任务/缓存进度结构不变。
- 输出兼容：A 保留 `steps/final_answer/summary`；B 保留 `questions/options/correct_answer/explanation`；C 保留开放问题、参考答案、评分点、追问和总结字段。

### 4.2 study：学生引导（已迁移）

- 入口：`apps/study/guidance_views.py:start_guidance`、`guidance_reply`；旧 `apps/study/ai_helper.py` 只保留同步函数签名并转发公共组件。
- 处理链：缺少预生成 C 内容时调用 `guidance_generate`；学生每轮回答调用 `guidance_evaluate`。
- 输入：题干、参考答案、学生回答和当前引导上下文。
- 错误策略：配置/模型失败时返回固定安全文案或空字典；C 实时生成失败以及既有连续无效回答条件仍按原契约降级 B，不泄露 provider 原始错误。
- 持久化：继续写 `AIGuidanceSession.content_log_json` 的问题、回答、步数和降级状态；API 地址、参数和 envelope 不变。

### 4.3 missions：教师引导评价（已迁移）

- 入口：`apps/missions/views.py:start_teacher_guidance`、`teacher_guidance_reply`。
- 处理链：预生成 B/C 内容仍从题目答案 JSON 读取；C 回复通过 `teacher_guidance_evaluate` 调用 `GuidanceComponent.evaluate_teacher_reply`。
- 错误策略：配置错误、响应错误和 provider 错误转为固定用户可见兜底，不展示环境变量名；旧 `_call_qwen` 已停用。
- 持久化：沿用当前进程内教师引导 session 数据结构和原 API envelope，本次迁移不新增数据库表。

### 4.4 study/photo：拍照识题（已迁移）

- 入口：`apps/study/photo_views.py:photo_create_question`。
- 处理链：图片经 `image_codec` 校验、压缩并转换安全多模态输入 -> `photo_recognize` -> `VisionParserComponent.recognize_photo` -> JSON 对象。
- 错误策略：组件/编码/网络/Schema 异常转换为固定安全错误；日志和 traceback 不保留完整 base64、本地路径或签名 URL；HTTP 重试统一由 `AIClient` 处理。
- 持久化：继续创建/更新 `ExamPaper`、`ExamQuestion`、`QuestionOption`、`QuestionImage`、`ExamPage`、`AIParseResult`，然后触发既有答案生成任务。

### 4.5 parser：位置、整页和逐题解析（已迁移）

- 入口：`apps/parser/tasks.py:parse_paper_task`、`reparse_question_task`、`reparse_page_task`，以及 `position_service.py`、`question_parse_service.py` 薄适配层。
- 位置：`vision_position_detect`，模型审计名保持 `qwen3.7-plus-position`。
- 整页：`vision_page_parse`；逐题：`vision_question_parse`。题型中文标签保存在非提示模块 `apps/parser/question_types.py`。
- 错误策略：固定错误码分别为 `POSITION_DETECTION_FAILED`、`QUESTION_PARSE_FAILED`、`PAPER_PARSE_FAILED`、`QUESTION_REPARSE_FAILED`、`PAGE_REPARSE_FAILED`；provider 原文、图片路径和 base64 不进入用户错误或日志。
- 持久化：保持 `ParseTask`、`ExamPage`、`ExamQuestion`、`QuestionOption`、`QuestionImage`、`AIParseResult.raw_response/response_json/latency_ms/model_name` 语义，以及原 Celery task 名称、参数和重试次数。

### 4.6 courses：课程资料框选识题（已迁移，Task10 补漏）

- 入口：`apps/courses/views.py:material_ai_recognize`，URL、权限检查、`image_url/page/crop_region` 参数和成功/未识别 envelope 保持不变。
- 处理链：可选框选裁剪 -> 安全图片输入 -> `course_material_recognize` -> `VisionParserComponent.recognize_course_material` -> 专用成功/错误联合 Schema。
- 模型：Qwen `qwen3-vl-plus`，300 秒；视图中不再存在 prompt、model、Key、URL 或私有 `_call_ai_multimodal` 调用。
- 错误策略：组件、codec 或 PIL 异常只返回固定 400 `detail=AI 识别失败`；内部 helper 在创建错误前清空本地路径、data URI、base64 和 provider 原文，日志仅记录异常类名。
- 持久化：本接口仍只返回识别 JSON；后续 `import_question` 按原流程决定是否创建课程题目，本入口不新增写库副作用。

### 4.7 courses：变式题生成与 DeepSeek 二次校验（已迁移）

- 入口：`apps/courses/tasks.py:generate_variant_task`、`batch_generate_variants_task` 及对应 views；`apps/courses/ai_service.py` 仅保留旧模块级签名的薄转发。
- 输入：原题题干、题型、选项、答案、解析、详解、难度、知识点与 `variant_mode`。
- 处理顺序：`variant_generate`（Qwen）-> `VariantValidator` 程序硬校验 -> `variant_verify_deepseek`（DeepSeek）。
- DeepSeek 保留策略：DeepSeek 校验仍启用；密钥缺失时只执行既有“显式跳过 AI 校验”分支；校验不通过或请求失败时，仅额外调用 DeepSeek 校验一次，不重新生成变式题。DeepSeek 故障绝不切换成 Qwen 校验，也不会把 Qwen 结果伪装成 DeepSeek 结果。
- 错误策略：生成/校验响应均经严格 Schema；Celery 仍 `max_retries=2`、30 秒指数退避；任务失败写固定状态和脱敏错误。
- 持久化：保持 `VariantTask.generator_result`、`verifier_result`、`generated_question`、`status`、`error_message`、`completed_at`；成功后继续创建 `ExamQuestion`、`QuestionOption` 和可选 `CourseQuestionLink`。

## 5. 兼容契约

- UniApp/REST URL、请求参数、权限和响应 envelope 不因 AI 内部替换而改变。
- `generate_variant_task`、`batch_generate_variants_task`、parser/review task 的名称、签名、进度和重试语义保持不变。
- `ExamQuestion`、`AIParseResult`、`AIGuidanceSession`、`VariantTask` 的既有字段含义保持不变。
- `apps/study/ai_helper.py`、`apps/courses/ai_service.py` 和 `apps/common/ai_service.py` 仅作为兼容适配器；它们不包含 provider HTTP、Python 内嵌提示词或硬编码 URL。

## 6. 已删除的旧实现

在删除前已确认无活跃生产 import，并由迁移后的行为测试保护。已删除：

- `apps/common/ai_prompts.py`、`apps/common/ai_prompts.py.bak`；
- `apps/courses/prompts.py`；
- `apps/parser/services/qwen_text_service.py`、`qwen_vl_service.py`；
- `apps/parser/prompts/page_parse_prompt.py`、`position_prompt.py`、`question_parse_prompt.py` 及空包文件。

parser 旧 prompt 文件中的唯一非提示数据 `QUESTION_TYPE_LABELS` 已移至 `apps/parser/question_types.py`，没有复制任何提示词。所有运行时提示词现只在 `config/ai_config.cfg`。

## 7. 验证状态

- 删除前保护套件：562 项通过。
- Task10 新增入口采用 RED -> GREEN：先复现缺 task key/旧私有调用失败，再通过公共组件修复；路由、Schema、权限、crop、envelope 和安全失败边界均有自动化测试。
- 最终集中修复后完整相关套件：723 项通过；`python manage.py check` 为 0 issue；Python compile/关键模块 import 通过；`git diff --check` 通过。
- 静态扫描结果：`apps/config` 中 Qwen 3.6 为 0 匹配；生产 Python 内嵌提示词为 0 匹配；已删除模块 import 为 0 匹配；`httpx.Client` 仅存在于公共客户端（以及测试），Key/兼容 URL 字样仅存在于 cfg 引用和测试夹具。
- 上述是本地单元/模拟/数据库契约验证；真实供应商证据另见 Task11，不能用本地测试替代。

## 8. Task11 受控冒烟命令状态（2026-08-03）

- 已实现 `python manage.py ai_smoke_test --provider qwen --live` 与 `python manage.py ai_smoke_test --provider deepseek --live`。命令仅通过公共题目探查组件或 DeepSeek 结果校验组件调用 cfg 中的固定 task，不包含独立提示词、URL、Key、模型、超时、HTTP 或回退路由。
- `--live` 是强制显式开关；缺少该开关时，在加载配置和构造 AI 客户端之前以非零退出码拒绝执行。成功输出仅包含 provider、cfg 配置模型、`status=ok`、耗时和 `schema=valid`；失败仅输出固定类别与退出码，不输出请求、响应或异常原文。
- 命令单元测试使用注入客户端完成零联网验证，覆盖 Qwen/DeepSeek task 隔离、严格 Schema、摘要白名单、配置/传输或超时/HTTP/响应分类、退出码、客户端清理和 traceback 脱敏。
- 本地实现证据：Task11 命令定向测试 15 项通过，本轮最终相关回归 723 项通过，Django `check` 为 0 issue；这些是组件和命令的模拟/本地证据，不等同于供应商调用成功。
- 历史受限证据：首次 Qwen `--live` 的输出在上下文切换时被截断，结果不可恢复；首次 DeepSeek `--live` 返回安全分类 HTTP 401，且没有回退到 Qwen。上述历史记录不曾被记作成功。
- 2026-08-03 用户明确批准追加一次 Qwen 真实调用，并明确 DeepSeek 使用与 Qwen 相同的阿里 API URL/Key；本地 `.env` 已只在未提交状态下完成对应映射，不在本文记录任何 URL 或 Key 值。
- Qwen 追加真实冒烟成功：`provider=qwen model=qwen3.7-flash status=ok latency_ms=16191 schema=valid`。
- DeepSeek 追加真实冒烟成功：`provider=deepseek model=deepseek-v4-pro status=ok latency_ms=6074 schema=valid`；调用仍使用独立 DeepSeek task，未回退到 Qwen。
- Task11 当前结论：两个最小真实供应商调用均成功并通过各自 Schema；该证据只证明受控最小冒烟成功，不等同于所有业务场景的真实数据 E2E。
