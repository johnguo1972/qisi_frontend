# A/B/C 模式答案双模型验证与仲裁设计

## 1. 背景与目标

题目 `019fa8a0-9397-7101-8180-545551f3f33f` 在执行 AI-A 模式时，Qwen 只收到探查结果中的题干，未收到完整选项、题库答案和解析，因此错误返回 `missing_conditions`。本设计在不改变现有前端按钮、API 地址和数据库表结构的前提下，为 A、B、C 三种模式建立统一的题目上下文、答案验证和双模型仲裁流程。

目标如下：

- A/B/C 只在用户手工点击对应按钮或“一键全部 AI 处理”后执行，禁止自动触发。
- Qwen3.7-plus 生成模式答案时收到完整题面、题库已有答案和解析。
- 发生冲突或题目没有参考答案时，使用 DeepSeek V4 Pro 思考模式进行验证。
- DeepSeek 第一阶段相对 Qwen 独立：它接收完整题面、题库答案和解析，但不接收 Qwen 结果。
- 只有存在冲突、低置信度或内容异常时，才进入包含全部候选结果的第二阶段综合复核。
- 验证和仲裁全部成功后才覆盖对应模式旧结果；失败时保留旧结果。
- URL 和 API Key 仅从 `.env` 读取；模型路由、参数和提示词仅从 `config/ai_config.cfg` 读取。
- 模型请求超时统一为 300 秒。

## 2. 范围与兼容性

### 2.1 包含范围

- 题目完整上下文构建。
- A/B/C 模式的 Qwen 生成、答案标准化、DeepSeek 验证和结果仲裁。
- 单模式 Celery 任务中的原子保存、进度、失败保护和重复任务防护。
- 现有 `ai_answer_a`、`ai_answer_b`、`ai_answer_c` 和 `ai_verifier_result` JSON 字段的扩展使用。
- 相关配置、提示词、自动化测试、真实模型测试和教师页面端到端验收。

### 2.2 不包含范围

- 不改变“AI 探查”自身的业务定义。
- 不恢复任何自动 AI 生成逻辑。
- 不新增数据库字段或迁移。
- 不改变现有前端接口地址、按钮含义或响应 envelope。
- 不修改 `./front` 以外的任何文件。

## 3. 总体架构

现有调用入口保持不变，单模式任务将内部生成逻辑委托给公共仲裁组件：

```text
用户点击 AI-A / AI-B / AI-C
             ↓
现有 API 与 single_mode_ai_process_question
             ↓
QuestionContextBuilder
             ↓
ModeAnswerArbitrator
   ├─ ModeAnswerGenerator（Qwen3.7-plus）
   ├─ AnswerNormalizer
   ├─ ModeContentValidator
   └─ DeepSeekAnswerVerifier
             ↓
验证成功后原子写入 ai_answer_a/b/c
             ↓
保存 verification 审计摘要与共享验证缓存
```

### 3.1 `QuestionContextBuilder`

从 `ExamQuestion` 及现有 AI 字段构建稳定 DTO，至少包含：

- `stem`、`stem_html`、`material`、`raw_text`
- 按标签排序的完整选项
- `question_type`、`subject`、`difficulty`
- 年级、学期、章节和知识点等可用属性
- `tables`、`subquestions`
- 图片 URL、`ai_vision_extract` 中的视觉事实
- `answer`、`analysis`、`solution`、`raw_explanation`
- 当前目标模式 A、B 或 C

选择题缺少选项、图片题既无图片又无可用视觉信息等不可恢复的数据问题，应在调用模型前失败，不允许用不完整题面生成正式答案。

### 3.2 `ModeAnswerGenerator`

按目标模式调用 Qwen3.7-plus。A/B/C 复用同一上下文 DTO 和公共调用内核，但分别读取 `mode_a_answer`、`mode_b_answer`、`mode_c_answer` 的提示词与 Schema。

题库答案和解析必须标记为“待验证的参考材料，可能存在错误”。Qwen 需要基于题面重新求解，并返回显式 `final_answer`，不得依赖从自然语言正文中猜测答案。

### 3.3 `AnswerNormalizer`

按题型标准化候选答案：

- 单选题统一为大写选项字母。
- 多选题去除分隔符、转为大写并按选项顺序排列。
- 判断题统一为稳定布尔语义。
- 数值题规范空格和可安全处理的单位表达。
- `missing_conditions`、空值和不存在的选项标记为无效答案。
- 主观题不使用简单字符串相等作为最终语义判定。

标准化器不擅自改变数学意义；不能确定等价性的答案交由验证模型处理。

### 3.4 `ModeContentValidator`

在仲裁前后执行确定性质量门禁：

- 输出满足对应模式 Schema。
- `final_answer` 与仲裁后的可信答案一致。
- 不得在上下文完整时声称“缺少选项”或“信息不足”。
- 不得引用题面不存在的选项或数据。
- 公式、步骤中的显式计算结果不得与最终答案矛盾。
- A/B/C 的必填字段保持现有前端兼容结构。

无法通过确定性规则确认的语义冲突进入 DeepSeek 第二阶段，不由本地代码武断裁决。

### 3.5 `DeepSeekAnswerVerifier`

提供两个稳定任务：

- `deepseek_independent_verify`：第一阶段重新解题和验证题库资料。
- `deepseek_final_review`：第二阶段综合复核全部候选并生成最终模式内容。

两个任务都使用 DeepSeek V4 Pro，显式传递 `enable_thinking=true`、`reasoning_effort=high`，并使用 300 秒请求超时。

### 3.6 `ModeAnswerArbitrator`

统一编排 A/B/C，负责选择调用阶段、比较标准化答案、判断内容是否可采用、生成审计摘要，并返回“可提交结果”或明确失败。该组件不直接保存数据库；现有任务在成功后负责原子持久化。

## 4. 模型输入与输出契约

### 4.1 Qwen 输入

Qwen 接收完整题目 DTO，包括题库已有答案、解析和解题过程。参考材料必须标注为可能有误，要求模型先重新求解再判断参考内容。

Qwen 输出至少包含：

```json
{
  "final_answer": "C",
  "mode_content": {},
  "reference_answer_valid": true,
  "confidence": 0.95
}
```

兼容适配层把 `mode_content` 映射回现有 A/B/C 前端依赖的 `steps`、`questions`、`final_answer`、`summary` 等字段。

### 4.2 DeepSeek 第一阶段输入

第一阶段接收：

- 作答所需的全部题面信息。
- 题库已有答案、解析、解题过程；没有时明确为空。
- 当前目标模式，以便同时生成可替代的模式候选内容。

第一阶段不得接收：

- Qwen 最终答案。
- Qwen 推导过程。
- Qwen A/B/C 模式内容。

因此“独立”表示相对 Qwen 独立，而不是对题库参考答案完全盲解。提示词必须明确题库资料可能有误，要求先根据题面重新计算，再验证参考材料。

DeepSeek 第一阶段输出至少包含：

```json
{
  "independent_answer": "C",
  "independent_reasoning_summary": "基于题面重新求解后的简要依据",
  "key_facts": [],
  "reference_answer_valid": true,
  "reference_analysis_valid": true,
  "reference_issues": [],
  "confidence": 0.98,
  "mode_content": {}
}
```

### 4.3 DeepSeek 第二阶段输入

第二阶段接收：

- 完整题目 DTO。
- 题库答案和解析。
- Qwen 的结构化结果及模式内容。
- DeepSeek 第一阶段结果。
- 本地标准化和规则校验产生的冲突清单。

候选内容使用“候选甲/乙/丙”等中性标签，避免在裁判提示词中通过模型名称暗示偏好。第二阶段必须返回可信答案、候选错误说明、Qwen 内容能否采用，以及必要时修正后的完整模式内容。

不保存模型隐藏的完整思考过程，只保存简要依据和裁决结果。

## 5. 详细数据流与仲裁规则

记：

- `R`：标准化后的题库参考答案。
- `Q`：标准化后的 Qwen 答案。
- `D`：标准化后的 DeepSeek 第一阶段答案。

### 5.1 题目有参考答案

1. Qwen 使用完整上下文生成目标模式答案。
2. 若 `Q = R`，且模式内容通过全部质量门禁，则采用 Qwen 结果，不调用 DeepSeek。
3. 若 `Q = R` 但内容出现结构错误、缺失条件、推导矛盾或低置信度，则进入 DeepSeek 第一阶段；必要时进入第二阶段。
4. 若 `Q != R`，执行 DeepSeek 第一阶段。DeepSeek 看见题库资料，但看不见 Qwen 结果。
5. 若 `D = R != Q`，可信答案为 `R/D`；拒绝 Qwen 内容，优先使用通过 Schema 的 DeepSeek 模式候选。候选不合格时进入第二阶段。
6. 若 `D = Q != R`，可信答案为 `Q/D`；只有 Qwen 内容通过质量门禁且关键事实与 DeepSeek 独立依据一致时才采用 Qwen，否则使用 DeepSeek 候选或进入第二阶段。
7. 若 `R`、`Q`、`D` 全部不同，必须进入第二阶段；以 DeepSeek 最终复核结论为准，并由第二阶段输出完整模式答案。
8. 即使答案字面一致，只要题库解析错误、DeepSeek 无法提供明确依据、验证字段自相矛盾或置信度低于阈值，也必须升级复核。

### 5.2 题目没有参考答案

1. Qwen 生成目标模式答案。
2. 必须执行 DeepSeek 第一阶段。
3. 若 `Q = D` 且 Qwen 内容通过质量门禁，则采用 Qwen 结果。
4. 若 `Q = D` 但 Qwen 内容不合格，则采用合格的 DeepSeek 模式候选；候选也不合格时进入第二阶段。
5. 若 `Q != D`，进入第二阶段综合复核，以第二阶段的可信答案和模式内容为准。
6. 若 DeepSeek 判定题目条件确实不足，不保存猜测答案，返回需要人工检查。

### 5.3 必须进入第二阶段的条件

- 三方答案全部不同。
- 无参考答案时 `Q != D`。
- Qwen 与参考答案冲突且第一阶段结果不足以安全选择内容。
- DeepSeek 置信度低于配置阈值。
- `reference_answer_valid` 与 `reference_analysis_valid` 或简要依据相互矛盾。
- Qwen 出现 `missing_conditions`、不存在的选项或题面外事实。
- 最终选项一致但关键推导、计算或模式内容存在语义冲突。

## 6. 配置设计

### 6.1 `.env`

只保存阿里 AI 的 API Key、OpenAI 兼容地址和 Host 等敏感连接信息。DeepSeek 与 Qwen 使用已确认的阿里连接配置。不得把 Key 写入 cfg、日志、异常文本、测试快照或文档。

### 6.2 `config/ai_config.cfg`

新增或完善以下任务配置：

```ini
[mode_answer]
primary_model = qwen3.7-plus
timeout = 300

[deepseek_independent_verify]
model = vanchin/deepseek-v4-pro
enable_thinking = true
reasoning_effort = high
timeout = 300
confidence_threshold = 0.80

[deepseek_final_review]
model = vanchin/deepseek-v4-pro
enable_thinking = true
reasoning_effort = high
timeout = 300
```

实际 section 名称应遵循现有配置加载器的 task key 规范。所有提示词和允许的模板变量均保存在 cfg；业务代码不得嵌入另一套完整提示词。

`enable_thinking` 和 `reasoning_effort` 必须进入 OpenAI 兼容请求的实际参数，而不是只作为提示词文字。

## 7. 超时、重试与并发

- 每次模型请求超时 300 秒。
- Celery 软超时建议 330 秒，硬超时建议 360 秒，确保任务层不会先于模型请求被终止。
- 网络中断、429 和 5xx 最多自动重试一次。
- 空响应或不可解析 JSON 先走现有安全修复；仍无效时最多重新调用一次。
- 401、403、配置错误、Schema 输入错误和明确缺少题面数据不重试。
- DeepSeek 必要验证失败时，存在冲突的 Qwen 结果不得落库为正式答案。

为 `question_id + mode` 建立任务锁。同一题目同一模式正在运行时返回现有任务状态，不重复调用模型；不同模式仍可分别手工触发。“一键全部 AI 处理”只负责编排用户明确触发的独立操作。

## 8. 持久化与失败保护

### 8.1 成功后替换

- 任务开始时不清空旧的 `ai_answer_a/b/c`。
- 生成、验证和仲裁全部成功后，在事务中一次性写入对应模式结果、验证摘要、处理时间和成功状态。
- 任一必要阶段失败时不覆盖旧模式答案。
- 原先没有结果时只返回失败状态，不保存未经验证的正式答案。

### 8.2 模式结果审计

在现有 `ai_answer_a/b/c` JSON 中增加兼容的 `verification` 节点：

```json
{
  "mode": "A",
  "final_answer": "C",
  "verification": {
    "status": "accepted",
    "context_hash": "sha256:...",
    "reference_answer": "C",
    "qwen_answer": "missing_conditions",
    "deepseek_answer": "C",
    "trusted_answer": "C",
    "selected_content_provider": "deepseek",
    "deepseek_thinking_enabled": true,
    "final_review_used": false,
    "confidence": 0.98,
    "warnings": ["Qwen 错误判断题目缺少选项"],
    "generated_at": "..."
  }
}
```

新增节点不能删除或改名现有前端依赖字段。

### 8.3 共享验证缓存

根据题干、选项、图片/视觉事实、题库答案、题库解析及关键属性生成 `context_hash`。将可跨模式复用的 DeepSeek 第一阶段答案验证摘要保存在现有 `ai_verifier_result` 中；模式专属候选内容仍只保存在对应 A/B/C 结果中。

题面、答案或解析变化会改变哈希，旧验证自动失效。复用只减少重复的独立解题调用，不允许把 A 模式内容复用为 B/C 模式内容。

## 9. 成本与延迟控制

| 场景 | 预期调用 |
|---|---|
| 有参考答案，Qwen 与参考答案一致且内容正常 | 1 次 Qwen |
| 无参考答案，Qwen 与 DeepSeek 一致 | 1 次 Qwen + 1 次 DeepSeek 第一阶段 |
| Qwen 与参考答案冲突且第一阶段可安全裁决 | 1 次 Qwen + 1 次 DeepSeek 第一阶段 |
| 冲突无法安全解决或内容异常 | 再增加 1 次 DeepSeek 第二阶段 |
| 后续处理其他模式且上下文未变化 | 复用第一阶段验证摘要 |

不固定对所有题目调用三次模型；只对无答案或高风险冲突增加验证成本。

## 10. 日志与安全

- 日志记录题目 ID、模式、task key、模型名、阶段、耗时、状态和错误分类。
- 不记录 API Key、Authorization 请求头、完整 base64 图片或隐藏思考过程。
- 原始模型内容只按现有诊断策略受控保存，不在普通日志中输出。
- 用户可见错误明确指出失败阶段，例如“DeepSeek 独立验证超时，原 A 模式答案未修改”。

## 11. 测试策略

### 11.1 单元测试

- 完整上下文包含题干、按序选项、图片/表格、题目属性、答案和解析。
- Qwen 输入包含题库参考资料。
- DeepSeek 第一阶段包含题库资料但不包含 Qwen 结果。
- DeepSeek 第二阶段包含题库、Qwen、第一阶段结果和冲突清单。
- 覆盖单选、多选、判断、数值、无效答案和主观题标准化。
- 覆盖 `Q=R`、`D=R`、`D=Q`、三方不同、无参考答案、低置信度、参考解析错误和模式内容错误。
- 验证 `enable_thinking=true`、`reasoning_effort=high` 和 300 秒超时进入实际 payload。

### 11.2 后端集成测试

- A/B/C 分别路由到对应任务和字段，不互相覆盖。
- 无用户手工操作时不产生 AI 任务。
- 重复点击同题同模式不重复创建模型调用。
- 必要验证失败时保留旧结果。
- 上下文哈希变化使缓存失效，未变化时允许跨模式复用验证摘要。
- 模拟 Qwen/DeepSeek 超时、429、5xx、空响应、截断 JSON、非法选项和 Celery 重复消费。

### 11.3 前端与构建验证

- 三个按钮分别只触发 A/B/C。
- 运行中禁止重复点击并显示进度。
- 成功后刷新对应内容，失败时显示原因且旧内容不变。
- 教师及管理员兼教师账号可以调用；无权限账号被拒绝。
- 执行 Django system check、相关后端测试、AI 组件回归、Celery 测试和 UniApp H5 生产构建。

### 11.4 指定题目真实端到端验收

使用题目 `019fa8a0-9397-7101-8180-545551f3f33f`。测试前备份当前 A/B/C JSON，依次通过教师页面手工触发三个模式。

共同验收要求：

- 模型收到完整 A/B/C/D 选项、题库答案 `C` 和原解析。
- 不出现 `missing_conditions` 或“没有提供选项”。
- 最终答案为 `C`，并正确说明 `37℃` 接近人体正常体温而非舒适环境温度。
- A/B/C 分别满足现有模式 Schema，字段各自落库且互不覆盖。
- `verification` 记录候选答案、可信答案、采用内容来源和是否使用最终复核。

冲突测试至少模拟：

```text
题库=C，Qwen=missing_conditions，DeepSeek 第一阶段=C
```

预期拒绝 Qwen 内容，可信答案为 `C`，采用合格的 DeepSeek 模式内容。

另模拟：

```text
题库=C，Qwen=A，DeepSeek 第一阶段=B
```

预期进入第二阶段，而不是任意选择候选答案。

## 12. 完成标准

- A/B/C 使用统一上下文和仲裁组件，现有接口及前端字段兼容。
- 所有模型 URL/Key 仍只来自 `.env`，新增路由、参数和提示词只来自 `ai_config.cfg`。
- DeepSeek 思考模式参数和 300 秒超时得到请求捕获测试证明。
- 自动化测试、Django 检查和 H5 构建通过。
- 模拟冲突、失败保护、重复任务和缓存失效测试通过。
- 指定题目的真实 Qwen/DeepSeek 调用及教师页面 A/B/C 操作通过。
- 完成报告分别陈述自动化测试、构建、模拟集成、真实模型调用和真实页面端到端结果；任何一层未执行均不得宣称端到端完成。

## 13. 文件与提交约束

- 所有实现修改严格限制在 `./front`。
- 不提交 `.env`、dump、媒体文件、构建产物、缓存或其他无关改动。
- 书面设计确认后再制定实施计划；实施按测试先行和小步提交执行。
