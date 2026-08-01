# AI 调用现状基线与公共组件迁移边界（2026-08-01）

> 范围：本文是源码阅读基线，不代表任何链路已经过运行时或外部模型验收。\
> 口径：**现状**只描述当前代码；**迁移目标**描述后续公共 AI 组件改造应达到的形态，不能倒推为已实现。所有迁移后的 AI HTTP 超时目标统一为 **300 秒**。

## 1. 人工审查清单

- [x] `AIReviewService`：旧四步和新六步入口、A/B/C、JSON 修复、题目字段写回。
- [x] 题目探查：`probe_and_norm`、规范化文本、知识点提示。
- [x] A/B/C 模式：全流程、单模式重跑、学生端和教师端消费契约。
- [x] 学生引导：预生成 B/C、C 实时生成和逐轮评价、C 到 B 降级。
- [x] 教师引导：B/C 会话读取和 C 轮次评价。
- [x] 拍照识题：图片压缩/OSS、视觉识别、题目/图片/AI 结果落库、后续答案生成。
- [x] 试卷解析：位置、整页、逐题视觉解析、合并后处理、重试与持久化。
- [x] 变式题：Qwen 生成、程序校验、DeepSeek 结果校验、题目落库。
- [x] DeepSeek：密钥缺失时的现状分支和“校验不通过再试一次”行为。
- [x] 持久化：`ExamQuestion` AI JSON 字段、`AIParseResult`、`AIGuidanceSession`、`VariantTask`、Celery/缓存状态。
- [x] 异常与重试：HTTP 重试、Celery 重试、可见降级和当前无重试点。

本清单用于人工交叉阅读，不以关键词是否出现作为测试或验收结论。

## 2. 现状总览

| 调用域 | 当前入口 | 当前直接客户端/模型 | 当前超时 | 主要持久化 | 迁移公共组件 |
| --- | --- | --- | --- | --- | --- |
| 审核 AI | `review` API/Celery、`common.batch_tasks` | `AIReviewService` -> `httpx` -> Qwen；按步骤路由 flash/plus | 300 秒 | `ExamQuestion.ai_*`、缓存进度 | `Probe`、`VisionParser`、`ModeA/B/C`、`ResultVerifier`、`AIClient` |
| 学生引导 | `study.guidance_views` | `ai_helper` -> Qwen `qwen3.6-flash` | 60 秒 | `AIGuidanceSession.content_log_json` | `Guidance`、`AIClient` |
| 教师引导 | `missions.views` | `_call_qwen` -> Qwen `qwen3.6-flash` | 60 秒 | 仅进程内 `_teacher_guidance_sessions` | `Guidance`、`AIClient`、会话仓储 |
| 拍照识题 | `study.photo_create_question` | `_call_vision_api` -> Qwen `qwen3-vl-plus` | 120 秒 | `ExamPaper`、`ExamQuestion`、`QuestionImage`、`ExamPage`、`AIParseResult` | `VisionParser`、`AIClient` |
| 试卷解析 | `parse_paper_task` | 位置 `QwenTextService`、逐题 `QuestionParseService`；均直连 Qwen | 位置 300 秒；逐题 180 秒 | `ParseTask`、`ExamPage`、`ExamQuestion`、`QuestionImage`、`AIParseResult` | `VisionParser(position/page/question)`、`AIClient` |
| 课程框选识题 | `courses.views.material_recognize_question` | 直接调用 `AIReviewService._call_ai_multimodal`，Qwen `qwen3.7-plus` | 300 秒（继承服务） | 仅响应识别 JSON | `VisionParser`、`AIClient` |
| 变式题 | `courses.tasks.generate_variant_task` | `VariantAIService` -> Qwen/DeepSeek | 300 秒 | `VariantTask`、新 `ExamQuestion`、`QuestionOption`、`CourseQuestionLink` | `VariantGenerator`、`ResultVerifier`、`AIClient` |

## 3. 按调用入口的现状与迁移目标

### 3.1 `common/review`：Probe -> Mode A/B/C -> ResultVerifier

| 项目 | 现状事实 | 迁移目标 |
| --- | --- | --- |
| 入口/函数 | `apps/review/views.py` 的审核 API 派发 `apps/review/tasks.py:single_ai_process_question`；其调用 `AIReviewService.process_question_full_v2`。批量路径在 `apps/common/batch_tasks.py`，仍调用旧 `process_question_full`。单模式任务重用已有 probe/vision 后调用 `solve_mode_a/b/c`。 | API/Celery 仅依赖明确的编排器；旧四步调用方迁到同一六步编排器后再删除旧入口。 |
| 输入 | `ExamQuestion` 的题干、题图（最多 5 张，经 OSS URL）、已有答案/解析；知识点识别另读取 `KnowledgePoint`。 | 公共 `QuestionContext`（题干、图片、答案、解析、学科、知识点）不可丢字段。 |
| 提示词来源 | `apps/common/ai_prompts.py`：`probe_and_norm`、`vision_extraction`、`solve_mode_a/b/c`、`verify_result`、`analyze_knowledge`；旧路径通过兼容包装 `knowledge_analysis`/`mode_*_answer`。 | 按公共组件保留提示词所有权，避免业务视图内嵌提示词。 |
| 模型与 HTTP | `AIReviewService._get_model` 优先级为 override > `settings.AI_MODEL` > 步骤默认；Probe/知识点/校验默认 `qwen3.6-flash`，视觉/三种求解默认 `qwen3.6-plus`。文本和多模态均用 `httpx.Client(timeout=300.0, trust_env=False)` 调 Qwen compatible endpoint。 | `AIClient` 统一认证、请求、300 秒超时、可观察日志和可注入模型路由。 |
| 解析 | `repair_json_string` 后 `json.loads`；无 choices 或 JSON 不合法抛 `AIRequestError`。 | 保持 JSON 修复与结构校验；组件只返回明确 DTO 或错误。 |
| 持久化 | `save_results_to_question` 写 `ai_probe_result`、`ai_vision_extract`、`ai_verifier_result`、`ai_knowledge_enrichment`、`ai_answer_a/b/c`；并匹配知识点、更新难度。任务写缓存进度，流程写 `ai_processing_status/ai_processed_at`。 | 保持字段名和答案 JSON 兼容契约，写入由统一仓储完成。 |
| 失败策略 | 客户端对 ReadTimeout/HTTPError 最多 3 次，等待 5/8/10 秒；六步按步骤捕获为 partial results，最终状态 `failed` 或 `success`。单审核任务本身 `max_retries=0`；旧单题任务 Celery 最多重试 2 次。 | 重试策略收敛到 `AIClient`/任务策略；调用方只区分成功、部分成功、失败。 |

**目标调用链**：`common/review -> Probe -> VisionParser -> ModeA/ModeB/ModeC -> ResultVerifier -> QuestionAIResultRepository`。

### 3.2 `study`：学生 Guidance 与 Mode C fallback

| 项目 | 现状事实 | 迁移目标 |
| --- | --- | --- |
| 入口/函数 | `apps/study/guidance_views.py:start_guidance` 和 `guidance_reply`。B/C 优先消费 `ExamQuestion.ai_answer_b/c`；C 无预生成题目时调用 `call_qwen_for_guidance_with_question`，C 每次答复调用 `call_qwen_for_guidance` 评价。 | `Guidance` 组件提供“生成步骤”和“评价回答”；视图仅负责鉴权、会话和响应。 |
| 输入/提示词 | 实时生成输入 `stem`/`answer`，生成系统提示词在 `apps/study/ai_helper.py:GUIDANCE_GENERATE_SYSTEM_PROMPT`；评价提示在 `guidance_reply` 内联。 | 将内联评价提示迁入 `Guidance` 提示词模块，输入保持题干、参考答案、学生回答。 |
| 模型与 HTTP | `ai_helper.py` 直连 Qwen `qwen3.6-flash`，`httpx.Client(timeout=60.0, trust_env=False)`。 | `AIClient`，超时统一 300 秒；模型路由由配置管理。 |
| 解析/持久化 | 生成步骤用 `response_format=json_object` 后 `json.loads`；实时 C 步骤转换为 `questions` 存进 `AIGuidanceSession.content_log_json`，每轮答复与步数也写该字段。 | 保持 session JSON 的 `ai_c_generated.questions`、`answers`、`step_index` 可读。 |
| 失败策略 | C 实时生成异常被吞并，降级 B、状态写 `downgraded`；C 评价异常返回“AI 评价暂不可用”；连续 2 次无效输入也降级 B。 | 明确、可观测的降级原因；不改变 C->B 的两类行为。 |

**目标调用链**：`study -> Guidance -> AIClient`；预生成 C 缺失时 `Guidance.generate_steps`，失败仍回退既有 B 数据/文案。

### 3.3 `missions`：教师 Guidance evaluation

| 项目 | 现状事实 | 迁移目标 |
| --- | --- | --- |
| 入口/函数 | `apps/missions/views.py:start_teacher_guidance` 与 `teacher_guidance_reply`。B/C 初始内容读取 `ai_answer_b/c`；仅 C 回复会调用 `_call_qwen` 做评价。 | 复用 `Guidance.evaluate_reply`，不要保留教师专用 HTTP 包装器。 |
| 输入/提示词 | `q.stem`、`q.answer`、`user_answer`；评价 system/user prompt 在 `teacher_guidance_reply` 内联。 | 迁入公共提示词，保持“1-2 句评价、指出不足、鼓励”的产品语义。 |
| 模型与 HTTP | `_call_qwen(..., model='qwen3.6-flash')`，`httpx.Client(timeout=60.0, trust_env=False)`。 | `AIClient`，超时统一 300 秒。 |
| 解析/持久化 | 提取 `choices[0].message.content` 作为纯文本；会话保存在进程内字典 `_teacher_guidance_sessions`，未落数据库。 | 公共组件返回文本；会话持久化迁移须另行设计，迁移本身不可假设已有数据库会话。 |
| 失败策略 | 缺密钥或任何异常直接返回括号包裹的用户可见文本，不重试。 | 保持用户可见兜底，但以标准错误码/日志代替字符串承载技术错误。 |

**目标调用链**：`missions -> Guidance.evaluate_reply -> AIClient`。

### 3.4 `study/photo`：拍照识题 -> VisionParser

| 项目 | 现状事实 | 迁移目标 |
| --- | --- | --- |
| 入口/函数 | `apps/study/photo_views.py:photo_create_question` -> `_call_vision_api`。 | `study/photo -> VisionParser -> AIClient`。 |
| 输入/提示词 | 上传的 `images` 或现有 `crop_file_path`，可关联 `paper_id/page_no`；提示词为同文件 `SYSTEM_PROMPT`，用户消息为固定“按 JSON 识别图片”。图片先 OSS 上传，失败压缩为 base64 data URL。 | `VisionParser` 接收图片列表和 photo schema；保留 OSS/base64 回退。 |
| 模型与 HTTP | Qwen `qwen3-vl-plus`，直连 `httpx.Client(timeout=120.0, trust_env=False)`。 | `AIClient`，超时统一 300 秒。 |
| 解析/持久化 | 先 `json.loads`，再正则提取 `{...}`；创建/复用 `ExamPaper`，写 `ExamQuestion`、选项、`QuestionImage`、`ExamPage`、`AIParseResult(raw_response/response_json/latency_ms/model_name)`，再异步触发旧 A/B/C 生成。 | 公共解析结果 DTO 映射到同一持久化字段；AI 原始结果审计字段继续保留。 |
| 失败策略 | timeout、连接断开、HTTP 状态、HTTP 错误均最多 3 次，等待 3/6/9 秒；最终向请求返回失败。 | 统一标准重试；不能删除拍照后的异步答案生成衔接。 |

### 3.5 `parser`：VisionParser(position/page/question)

| 子阶段 | 现状事实 | 迁移目标 |
| --- | --- | --- |
| position | `parse_paper_task` 调 `position_service.detect_question_positions`，后者用 `QwenTextService.detect_question_positions`；提示词来自 `apps/parser/prompts/position_prompt.py`，输入为页图。模型 `qwen3.6-plus`，`httpx` 300 秒，3 次 timeout/HTTP 重试（5/8/10 秒）。 | `VisionParser.position` + `AIClient`，保持 position JSON 和 300 秒。 |
| page | `QwenVLService.parse_page` 定义在 `apps/parser/services/qwen_vl_service.py`，提示词来自 `page_parse_prompt.py`，模型 `qwen3-vl-plus`、直连 `httpx` 120 秒、一次调用。当前 `rg` 未发现它被 `parse_paper_task` 调用。 | 为兼容未来/独立整页调用保留 `VisionParser.page` 适配器；若确认没有路由调用，再单独删除旧服务。超时目标 300 秒。 |
| question | `parse_paper_task` 的 stage 2 调 `parse_questions_stage2` -> `QuestionParseService.parse_question`；提示词来自 `question_parse_prompt.py`，输入为位置结果、相关页图和页号。模型 `qwen3-vl-plus`，直连 `httpx` 180 秒、一次调用。 | `VisionParser.question` + `AIClient`，超时统一 300 秒。 |
| 编排/解析/持久化 | 任务先建 `ParseTask`，转 PDF/图片，写 `ExamPage`、位置 `AIParseResult`，逐题解析、合并/后处理/裁图，最后写 `ExamQuestion`、`QuestionOption`、`QuestionImage`、`AIParseResult`。 | 编排仍归 parser，公共组件仅收敛模型调用与解析契约。 |
| 失败策略 | `parse_paper_task` Celery `max_retries=2`、指数 30 秒；单题/单页重解析各 `max_retries=1`、指数 15 秒；周期任务标记并重试过期任务。服务层位置有 HTTP 重试，page/question 当前无服务层重试。 | 任务重试语义保持；HTTP 重试实现统一，避免双重重试预算不透明。 |

**目标调用链**：`parser -> VisionParser.position/page/question -> AIClient -> parser save/merge`。

### 3.6 `courses`：框选识题与 VariantGenerator -> DeepSeek ResultVerifier

| 项目 | 现状事实 | 迁移目标 |
| --- | --- | --- |
| 框选识题入口 | `apps/courses/views.py:material_recognize_question` 读取资料图片，可按 `crop_region` 裁剪，直接调用私有 `AIReviewService._call_ai_multimodal`，内联 JSON 提示词并自行处理 Markdown 围栏/截断括号。模型硬编码 `qwen3.7-plus`。 | 改调 `VisionParser` 公共 API；不能继续调用另一服务私有方法；保留当前响应 JSON 格式和可恢复截断修复。 |
| 变式题入口 | `apps/courses/tasks.py:generate_variant_task`。输入为原题 stem/type/answer/analysis/solution/difficulty/knowledge_points/options 与 `variant_mode`；生成提示来自 `apps/courses/prompts.py:VARIANT_SYSTEM_PROMPT` + `build_variant_user_prompt`。 | `VariantGenerator.generate` 接收同样原题 DTO 和变式模式。 |
| 生成模型与 HTTP | `_get_ai_model('qwen3.7-plus')`（可由 settings 覆盖），`VariantAIService.call_ai` 用 `httpx` 300 秒；`repair_json_string` 后 JSON 解析。 | `AIClient` 统一调用，超时 300 秒。 |
| 程序校验 | 生成 JSON 先交 `VariantValidator.validate`；失败是硬失败。 | **必须保留**；它不是 DeepSeek 的替代品。 |
| DeepSeek 校验 | verifier 提示来自 `VERIFIER_SYSTEM_PROMPT` + `build_verifier_user_prompt`；读取 `DEEPSEEK_API_KEY`，调用 `https://api.deepseek.com/v1/chat/completions` 与 `DEEPSEEK_MODEL`（默认 `deepseek-v4-pro`）。密钥缺失时记录 warning 并跳过 AI 校验；校验 `passed=false` 或 `AIRequestError` 时额外再试一次。 | `ResultVerifier.deepseek` 必须保留独立密钥、模型路由、结果字段和“至少再试一次”契约。 |
| 持久化/失败 | 写 `VariantTask.generator_result/verifier_result/generated_question/status/error_message/completed_at`；成功再创建 `ExamQuestion`、选项和可能的 `CourseQuestionLink`。Celery `max_retries=2`，30 秒指数重试。 | 公共组件不吞掉任务状态；生成、程序校验、DeepSeek 结果都必须可审计。 |

**目标调用链**：`courses -> VariantGenerator -> VariantValidator -> DeepSeek ResultVerifier -> VariantTask/ExamQuestion repository`。

## 4. 配置职责表

| 配置/密钥 | 当前读取位置 | 职责 | 迁移约束 |
| --- | --- | --- | --- |
| `QWEN_API_KEY` | 多个服务直接 `os.environ.get`；`config/settings.py` 也暴露 `QWEN_API_KEY` | Qwen compatible endpoint 认证 | 仅 `AIClient` 读取；不写入日志或文档样例。 |
| `AI_MODEL` | `config/settings.py`、`AIReviewService._get_model` | 审核链默认模型 | 保持 override 优先级，路由移入配置对象。 |
| `AI_MODEL_QWEN_36_FLASH/PLUS`、`AI_MODEL_QWEN_37_FLASH/PLUS` | `courses.tasks._get_ai_model` 以 `getattr` 读取 | 课程任务模型别名 | 显式纳入统一模型路由，避免只在 courses 生效。 |
| `DEEPSEEK_API_KEY` | `VariantAIService` | DeepSeek 校验认证 | 不与 Qwen 密钥混用；缺失行为需保留并可观测。 |
| `DEEPSEEK_MODEL` | `courses.tasks._get_ai_model` | DeepSeek 校验模型，默认 `deepseek-v4-pro` | 显式成为 `ResultVerifier` 路由。 |
| HTTP timeout | 各文件硬编码 60/120/180/300 秒 | 请求上限 | 迁移后所有 AI HTTP 请求使用 300 秒单一配置。 |

## 5. 模型路由表

| 能力 | 当前默认/硬编码模型 | 备用/覆盖 | 迁移后路由 |
| --- | --- | --- | --- |
| Probe、知识点、结果校验 | `qwen3.6-flash` | `AI_MODEL` 或任务 `model` 可覆盖 | `Probe`/`ResultVerifier` 默认 flash。 |
| Vision、A/B/C 求解 | `qwen3.6-plus` | 同上 | `VisionParser`/`ModeA/B/C` 默认 plus。 |
| 学生/教师实时评价 | `qwen3.6-flash` | 当前无设置路由 | `Guidance` 经统一配置选择，默认保持 flash。 |
| 拍照、逐题/整页解析 | `qwen3-vl-plus` | 当前无 | `VisionParser.photo/question/page`。 |
| 位置检测 | `qwen3.6-plus` | 当前无 | `VisionParser.position`。 |
| 课程框选识题 | `qwen3.7-plus` | 当前无 | `VisionParser.course_crop`。 |
| 变式题生成 | `qwen3.7-plus` | `AI_MODEL_QWEN_37_PLUS` | `VariantGenerator`。 |
| 变式题结果校验 | `deepseek-v4-pro` | `DEEPSEEK_MODEL` | `ResultVerifier.deepseek`，保留。 |

## 6. 兼容契约表

| 契约 | 必须保持的行为 |
| --- | --- |
| A/B/C 结果 | `ai_answer_a/b/c` 仍是可 JSON 解码对象，带 `mode`、`model`、`generated_at`、确认/编辑字段；学生和教师引导可以读取其 `questions`、`hint`、`summary`、`final_answer`。 |
| Probe/Vision/Verifier | `ai_probe_result` 提供 `normalized_text` 和可能的 `topic_tags_top3`；`ai_vision_extract`、`ai_verifier_result` 保持 JSON 审核可读。 |
| JSON 容错 | 继续处理 markdown 围栏、可修复 JSON；不可修复响应必须是显式错误，不可伪造成功。 |
| 学生降级 | C 无预生成数据时实时生成；实时生成失败或连续 2 次无效输入必须降到 B，并保留当前响应的降级语义。 |
| 拍照结果 | 图像上传失败时仍可 base64；识别后保持创建题目、图片、`AIParseResult` 和异步答案生成。 |
| Parser 结果 | 位置/逐题 JSON、跨页合并和人工复核字段不能因 HTTP 层收敛而变化。 |
| 变式题双重验证 | `VariantValidator` 硬校验 + DeepSeek 结果校验都保留；DeepSeek 失败/不通过时额外重试一次，密钥缺失仍为当前跳过分支。 |
| 失败可见性 | 审核链的 partial/error 字段、任务状态和现有用户兜底文案不能被统一组件静默吞掉。 |

## 7. 旧代码删除清单（迁移完成后，非本次操作）

以下均为候选删除项，删除前必须先迁移调用方、验证兼容契约并确认无路由/任务引用。

1. `apps/common/ai_service.py` 的 `_call_ai`/`_call_ai_multimodal` HTTP 实现，替换为 `AIClient` 后删除；`AIReviewService` 保留为编排兼容外壳或在所有调用方迁走后删除。
2. `apps/study/ai_helper.py` 的两个 Qwen HTTP 函数，替换为 `Guidance` 后删除；其中的生成提示迁移而不是丢弃。
3. `apps/missions/views.py:_call_qwen`，教师评价切至 `Guidance` 后删除；同时处理进程内会话仓储的独立改造。
4. `apps/study/photo_views.py:_call_vision_api` 的请求/解析部分，替换为 `VisionParser.photo` 后删除；图片压缩和落库仍由边界层保留。
5. `apps/parser/services/qwen_text_service.py`、`qwen_vl_service.py`、`question_parse_service.py` 内的直连 HTTP 部分，替换为 `VisionParser` 适配器后删除。`QwenVLService.parse_page` 先确认无调用方，再删除整个旧服务。
6. `apps/courses/ai_service.py:VariantAIService` 的 HTTP 包装和模块级兼容函数，替换为 `AIClient` 后删除；DeepSeek 路由功能迁至 `ResultVerifier`，不可一并删掉。
7. `apps/courses/views.py` 的私有 `_call_ai_multimodal` 调用和局部 JSON 修复，替换为 `VisionParser.course_crop` 后删除重复实现。
8. `AIReviewService.process_question_full` 旧四步路径及 `common.batch_tasks`/拍照后触发的旧调用，仅在全部改用六步编排且完成兼容验证后删除。

## 8. 本次人工交叉核对记录

已用源码搜索确认：所有 `httpx.Client` 直连点、Qwen/DeepSeek endpoint、`AIReviewService` 调用方、`parse_paper_task` 及其 position/question 服务、学生/教师引导、拍照识题、课程框选识题与变式任务均已在以上条目中列出。特别确认：`QwenVLService.parse_page` 有实现但本次搜索未找到 `parse_paper_task` 调用；因此将其标为“定义未见任务调用”，而不是错误描述为现行主链步骤。

未执行外部 AI 请求、数据库写入或 Celery 任务；本文只证明当前源码覆盖，不能证明任一模型、密钥、网络、任务队列或持久化链路在运行环境可用。
