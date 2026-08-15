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
| `deepseek_independent_verify` | DeepSeek | `deepseek-v4-pro` | `DeepSeekIndependentVerifierComponent.run` | 独立答案、参考资料有效性、关键事实和模式内容严格 Schema |
| `deepseek_final_review` | DeepSeek | `deepseek-v4-pro` | `DeepSeekFinalReviewComponent.run` | 匿名候选最终仲裁和完整模式内容严格 Schema |
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

### 4.0 题目 AI 的手动触发策略（2026-08-03）

- 题目探查和 A/B/C 答案生成均为**仅手动触发**的操作。创建、导入、解析、保存、编辑、确认、拍照创建题目或页面加载，均不会自动发起题目探查，也不会自动发起 A/B/C。
- 前端仅提供以下五个明确点击操作，任何批处理也必须由用户显式选题后点击触发：

| 操作 | 精确处理范围 | 不会隐式执行的步骤 |
| --- | --- | --- |
| `一键全部 AI 处理` | `question_probe`、知识分析、视觉事实提取、A/B/C 以及 DeepSeek 校验 | 无；该操作只在用户明确点击后执行完整链路 |
| `AI 探查` | `question_probe`、知识分析及其属性持久化 | 视觉事实提取、A/B/C 和 DeepSeek 校验 |
| `A 模式` | `mode_a_answer` 及该结果必需的统一验证/仲裁 | 探查、知识分析、视觉事实提取和 B/C 生成 |
| `B 模式` | `mode_b_answer` 及该结果必需的统一验证/仲裁 | 探查、知识分析、视觉事实提取和 A/C 生成 |
| `C 模式` | `mode_c_answer` 及该结果必需的统一验证/仲裁 | 探查、知识分析、视觉事实提取和 A/B 生成 |

- 后端手动入口为：
  - `POST /api/v1/review/question/<question_id>/ai-process/`：一键全部 AI 处理；
  - `POST /api/v1/review/question/<question_id>/ai-process-probe/`：仅 AI 探查；
  - `POST /api/v1/review/question/<question_id>/ai-process-mode/<A|B|C>/`：仅所选答案模式。
- 批量入口同样只接受显式选题和显式点击，不能由保存、创建、导入、解析、拍照或页面加载信号间接调度。
- 目标题目不存在时，入口以终态 `skipped` / `question_not_found` 结束，且在此之前不创建 AI 客户端、不发起 AI 调用。
- 历史兼容任务 `apps.common.batch_tasks.single_generate_ai_answers` 已注册为禁用墓碑：仅返回 `automatic_generation_disabled`，从不调用 AI。保留该任务只为兼容旧任务名，不能作为自动生成入口。

### 4.1 common/review：题目探查、知识分析和 A/B/C 答案（已迁移）

- 入口：`apps/common/batch_tasks.py`、`apps/common/management/commands/generate_ai_guidance.py`、`apps/review/tasks.py`、`apps/review/views.py`、`apps/review/services/ai_review_service.py`。
- 兼容外壳：`apps/common/ai_service.py:AIReviewService` 保留原公开方法和 mock 注入点，不再拥有 provider HTTP、URL、Key 或提示词。
- 输入：题干、已有答案/解析、选项、题图、知识点和题目元数据，统一转换为 `QuestionInput`。
- 一键全部 AI 处理链：`question_probe` -> `knowledge_analysis` -> `vision_fact_extract` -> `mode_a_answer`/`mode_b_answer`/`mode_c_answer` -> DeepSeek 校验；探查入口只执行 `question_probe` 和 `knowledge_analysis` 并持久化属性；A/B/C 入口各自只执行已选模式，不隐式探查。
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
- 持久化：继续创建/更新 `ExamPaper`、`ExamQuestion`、`QuestionOption`、`QuestionImage`、`ExamPage`、`AIParseResult`；创建完成后不触发题目探查或 A/B/C，后续 AI 处理须由用户手动选择上述五个操作之一。

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

### 4.8 review：A/B/C 答案生成、独立验证与仲裁（2026-08-15）

#### 手动入口和完整上下文

- A、B、C 三个按钮及“一键全部 AI 处理”仍是唯一生成入口；创建、导入、解析、保存、页面加载和轮询都不会自动创建任务。单模式入口只生成所点模式，一键入口才显式编排全部模式。
- 每次生成使用同一份不可变题目上下文：题干、按 A/B/C/D 标签和保存顺序稳定整理的选项、题图 URL、表格、材料、子问题、题型、学科、难度、规范化题干、视觉事实、知识点，以及题库已有答案、已有解析和解答。图片、表格或读图事实不会在验证阶段被省略；没有的字段以安全空值表达，不猜测条件。
- A/B/C 首次生成分别调用 cfg 中的 `mode_a_answer`、`mode_b_answer`、`mode_c_answer`，统一使用 Qwen `qwen3.7-plus`。A 输出 3–5 步、最终答案和总结；B 输出按顺序的递进问题、严格 A/B/C/D 选项、正确选项、参考答案、解析、最终答案和总结；C 输出开放问题、参考答案、关键点、追问提示、最终答案和总结。

#### 快速路径和两阶段 DeepSeek

- Qwen 结果先经过确定性的答案整理、题目完整性预检和模式内容校验。答案整理明确覆盖选择题选项键与判断题真/假别名；其它题型只做可见文本整理，不宣称数值、单位或自由文本在语义上等价。模式内容校验检查现有 Schema 必填字段、顶层 `final_answer` 一致性，以及代码明确识别的 `missing_conditions` 和选项缺失声明。
- 快速路径采用明确客观题型 allowlist，只包含 `single_choice`、`multiple_choice`、`true_false` 及代码支持的中英文别名。选择题还必须至少有两个非空选项，标签必须是互异的单字母且内容互异；`computation`、`fill_blank`、其它自由作答题和所有未知/未来题型，即使 Qwen 答案与参考答案文本相同，也必须进入独立验证。Qwen 显式报告缺失条件、置信度低于阈值或格式非法时同样不能走快速路径。题面标明依赖图片/图表时，还必须存在题图 URL 或可用的视觉事实。
- 有有效参考答案且 Qwen 答案与其严格一致、模式内容完整有效、预检没有风险时才走快速路径，不调用 DeepSeek；没有显式置信度时不会伪造 `1.0`。共享缓存中已有同一 `context_hash` 的有效独立验证摘要时可复用验证结论，但仍重新生成并校验当前模式内容。
- 需要验证时，第一阶段固定调用 `deepseek_independent_verify`。它收到上述完整题目上下文，包括题库已有答案与解析，但明确不接收 Qwen 结果、候选冲突或其它候选来源信息；因此必须独立求解，再返回答案、简洁理由摘要、关键事实、参考答案/解析有效性、置信度和当前模式内容。
- 参考答案或解析不存在时，对应 DeepSeek 有效性字段允许缺失并按 `null` 处理；参考资料存在时则必须返回显式布尔值，否则安全失败。若 DeepSeek 声明参考答案有效但其独立答案与参考答案不一致，会记录稳定冲突并强制最终复核，不能把矛盾声明当成支持证据。
- 只有发生答案冲突、DeepSeek 低置信度、参考答案/解析有效性矛盾、模式内容失败、缺失条件、非法选项，或答案虽一致但关键事实不能按当前确定性规则精确覆盖时，才调用第二阶段 `deepseek_final_review`。第二阶段收到完整题目上下文、完整候选 A、完整候选 B、冲突清单和目标模式 Schema；候选来源被匿名化，不以 provider 名称影响判断。
- 仲裁先使用确定性答案门和内容门，再按 `Qwen / DeepSeek / 参考答案` 的严格相等关系选择路径。关键事实门采取保守策略：无法结构化确认等价就升级最终复核，不以语义猜测直接接受。最终复核仍失败、Schema 无效或可信答案与模式内容不一致时，整个模式生成失败关闭，不把未验证候选当成成功。
- Mode B 会逐项检查 Schema 中明确承载答案的 `correct_option`、`correct_answer`、`reference_answer` 等字段及顶层 `final_answer`：选项键统一标准化后必须彼此一致并与可信答案一致。自由文本解释不会被误当作选项键。Mode C 仅对明确的选项键答案做同类检查，不扩张到说明性文字。

#### 复用、公开输出与持久化

- `context_hash` 由题干、稳定排序选项、图片/视觉事实、表格和其它题目属性、已有答案及解析共同生成。题面、选项、图片事实、答案或解析变化都会使旧验证失效。
- `ai_verifier_result` 在单模式和两个完整手动流程中都只保存与模式无关的 DeepSeek 共享摘要：`context_hash`、独立答案、nullable 参考有效性、问题清单、关键事实和置信度。A 的步骤、B 的选择题、C 的开放问题等 `mode_content` 不进入共享缓存；旧 `ResultVerifierComponent` 的结果也不会覆盖它。完整流程存在任一模式错误时保留旧共享摘要。
- 对外和落库结果严格投影到既有 A/B/C 公共字段及安全 `verification` 摘要。仲裁接受候选后会复制结果，并把顶层 `final_answer` 写成与 `verification.trusted_answer` 相同的规范值，例如 `c` 写回为 `C`，不修改原候选对象。隐藏思维链、`reasoning_content`、provider 原始响应、请求消息、提示词、响应正文、URL、Key 和请求头均不返回、不落入模式答案，也不出现在命令错误或进度错误中。
- 单模式任务只有在生成、验证和仲裁全部成功后，才在一个 `transaction.atomic()` 内锁定题目行。写入前会基于锁定后的最新题干、选项、参考答案、解析及视觉上下文重建 `context_hash`；任何变化都以 `question_context_changed` 失败关闭，并保留旧模式答案、共享摘要、处理时间和状态。哈希一致时才同时写入所选 `ai_answer_a/b/c`、可安全共享的 `ai_verifier_result`、处理时间和成功状态。
- 模式答案中的 `provider`/`model` 审计字段来自实际 `mode_a_answer`、`mode_b_answer`、`mode_c_answer` task 路由；只为兼容保留但未改变执行路由的 `model` 入参不会伪造审计模型。

#### 超时、并发、API 和页面安全

- 每次 Qwen/DeepSeek HTTP 请求的 cfg 超时为 300 秒；单模式 Celery 软超时为 3800 秒、硬超时为 3900 秒。`question_id + mode` 使用 4200 秒锁，重复点击返回已有 task ID，不重复调用模型，不同模式可独立手动触发。
- 锁值包含任务所有者。正常完成、已处理失败、软超时或异常都在 `finally` 中主动释放，但只能通过原子 compare-and-delete 删除当前所有者自己的锁；所有者不匹配或后端不支持原子删除时保持锁到 TTL，绝不误删新任务的锁。
- 单模式 API 保持原成功 envelope，并返回真实 `task_id`、运行状态、模式和是否去重；非法模式、无权限和题目不存在仍按原契约处理。前端仅在用户点击后收集这些 task ID，并轮询到 `complete`、`partial`、`failed` 或 `skipped` 后停止，成功后刷新题目列表；每个按钮只显示自己的处理中状态。
- review 下的完整、探查、单模式、确认/编辑以及批量 AI 入口统一要求已认证的教师会话；学生、家长和仅管理员角色返回 403 且不会调度任务或修改 AI 数据，具备教师角色的管理员按教师会话策略允许访问。
- 页面打开、刷新和 `onShow` 不会发起生成或恢复旧轮询。`onHide`、`onUnload` 和组件卸载都会停止轮询并递增页面请求代次；任何在页面隐藏前启动、隐藏后才返回的提交、状态查询或刷新响应都会因代次不匹配被丢弃，旧请求也不能清除新请求的状态。

#### 配置边界

- provider、task、模型、提示词、思考参数、重试和超时路由只来自 `config/ai_config.cfg`；连接地址和凭据只由应用从 `.env` 指定的环境变量加载。业务代码、测试、日志和本文均不保存实际凭据或主机秘密。
- A/B/C 提示词把已有答案、解析和详解明确标为“待验证参考资料，可能错误”，要求先依据题面重新求解再核对；提示词只要求符合公共 Schema 的简洁步骤/说明，不请求 `reasoning_process`、思维链或隐藏推理。

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
- 最终集中修复后两组不重叠的相关套件共 769 项通过：纯 AI 677 项，review/DB 92 项；客观题型 allowlist 文件窄测 73 项、八项安全回归窄测和 prompt registry 均已包含在前述总数中。`python manage.py check` 为 0 issue，`git diff --check` 通过。
- 静态扫描结果：`apps/config` 中 Qwen 3.6 为 0 匹配；生产 Python 内嵌提示词为 0 匹配；已删除模块 import 为 0 匹配；`httpx.Client` 仅存在于公共客户端（以及测试），Key/兼容 URL 字样仅存在于 cfg 引用和测试夹具。
- 上述是本地单元/模拟/数据库契约验证；真实供应商证据另见 Task11，不能用本地测试替代。

## 8. 受控冒烟命令与历史状态

- 已实现 `python manage.py ai_smoke_test --provider qwen --live`、兼容默认的 `--provider deepseek --live`，以及显式 `--task deepseek_independent_verify` / `--task deepseek_final_review`。parser 将 task 当普通字符串接收，再由 `handle()` 的固定 allowlist 校验；因此任意 cfg key 和 provider/task 不匹配会在配置加载和 HTTP 客户端构造前拒绝，且非法原值不会被 argparse 回显。默认 Qwen 仍路由 `question_probe`，默认 DeepSeek 仍路由 `variant_verify_deepseek`。
- `--live` 是强制显式开关；缺少该开关时，在加载配置和构造 AI 客户端之前以非零退出码拒绝执行。DeepSeek 独立验证和最终复核只有在顶层响应 Schema、目标 A/B/C 实际模式 Schema、公共字段投影及 `ModeContentValidator` 的可信答案一致性检查全部通过后，才输出 `schema=valid`；空模式内容、错误模式结构、缺字段或最终答案冲突均按安全响应错误失败。成功输出仅包含 provider、cfg 配置模型、task 名、`status=ok`、耗时和 `schema=valid`；失败仅包含 provider、安全 task 名、固定类别、可选 HTTP 状态和退出码。提示词、消息、参考答案/解析、完整响应、响应正文、URL、Key、请求头及隐藏推理一律不输出。
- 真实失败按配置、网络/超时、HTTP provider 状态、Schema/响应和未知错误分别给出固定安全类别，不拼接原始异常或 provider 响应正文。命令单元测试使用注入客户端完成零联网验证，覆盖固定 task 路由、严格 Schema 夹具、provider/task 隔离、任意 task 拒绝、成功/失败摘要白名单、退出码、客户端清理和 traceback 脱敏。
- 下列 2026-08-03 记录属于旧版默认 task 的历史证据；它们不替代当前代码、当前凭据和当前网络下重新执行的 live smoke，也不等同于题目 API 或浏览器 E2E。
- 本地实现证据：Task11 命令定向测试 15 项通过，本轮最终相关回归 769 项通过，Django `check` 为 0 issue；这些是组件和命令的模拟/本地证据，不等同于供应商调用成功。
- 历史受限证据：首次 Qwen `--live` 的输出在上下文切换时被截断，结果不可恢复；首次 DeepSeek `--live` 返回安全分类 HTTP 401，且没有回退到 Qwen。上述历史记录不曾被记作成功。
- 2026-08-03 用户明确批准追加一次 Qwen 真实调用，并明确 DeepSeek 使用与 Qwen 相同的阿里 API URL/Key；本地 `.env` 已只在未提交状态下完成对应映射，不在本文记录任何 URL 或 Key 值。
- Qwen 追加真实冒烟成功：`provider=qwen model=qwen3.7-flash status=ok latency_ms=16191 schema=valid`。
- DeepSeek 追加真实冒烟成功：`provider=deepseek model=deepseek-v4-pro status=ok latency_ms=6074 schema=valid`；调用仍使用独立 DeepSeek task，未回退到 Qwen。
- Task11 当前结论：两个最小真实供应商调用均成功并通过各自 Schema；该证据只证明受控最小冒烟成功，不等同于所有业务场景的真实数据 E2E。
