# 启思AI导师 `front/` 系统处理流程

**日期**: 2026-06-23
**状态**: 已梳理 / 持续维护
**适用范围**: `D:\workspace\code\qidi\front`（Django + uniapp 版本）

> 本文是对 `front/` 目录端到端处理流程的梳理存档。所有 `文件:行号` 引用基于梳理时（2026-06-23）的代码状态，后续代码演进后可能漂移，定位时请以函数/类名为准。
>
> 注意：仓库根目录下还有 `backend/` + `miniprogram/`（Node/微信小程序版）和 `oversea/`（海外网关），它们与 `front/` **相互独立**。本文只描述 `front/`。

---

## 1. 总体架构与技术栈

`front/` 是 **Django 单体后端 + uniapp 移动前端** 的教育平台。核心价值链：**把一份试卷文档变成学生可做、可被 AI 引导的题目**。

| 层 | 技术 | 关键位置 |
|---|---|---|
| 后端框架 | Django 5 + DRF + SimpleJWT | `config/`、`apps/` |
| 异步任务 | Celery + Redis（broker/backend） | `config/celery.py`、`apps/*/tasks.py` |
| 数据库 | PostgreSQL | `config/settings.py` |
| AI 能力 | 通义千问（qwen3.6-plus 文本 / qwen3-vl-plus 视觉 / qwen3.6-flash 轻量） | `apps/common/ai_service.py`、`apps/parser/services/qwen_*` |
| 对象存储 | 阿里云 OSS + 本地 media | `apps/common/oss_service.py` |
| 短信 | 腾讯云 SMS | `apps/accounts/sms_service.py` |
| 前端 | uniapp（Vue3 + Vite + TS），三角色 | `uniapp/src/` |

**三类角色**：`teacher`（出题/审核/派任务）、`student`/`parent`（做题/错题/引导）、`admin`（平台/机构管理）。用户模型为自定义 `AUTH_USER_MODEL = 'accounts.UserAccount'`，以手机号为登录标识。

**Django apps 一览**：`accounts`(认证)、`common`(公共服务)、`institutions`(机构/班级)、`knowledge`(知识树)、`missions`(任务)、`papers`(试卷编排)、`parser`(解析引擎⭐)、`review`(审核编辑)、`study`(学习/答题/引导)、`wrongbook`(错题本)。

---

## 2. 端到端主线

```
        【题目生产侧 —— 教师】                              【学习消费侧 —— 学生】
┌──────────────────────────────────────────────────┐   ┌───────────────────────────────┐
│ 1. 教师上传 .docx 试卷                              │   │ 8. 邀请码/申请加入班级          │
│      ↓ POST /api/v1/papers/upload/                  │   │      ↓ apps/institutions       │
│ 2. Celery: Word→PDF→页面图(100DPI→300DPI)           │   │ 9. 接收任务 mission            │
│      ↓ apps/parser/tasks.parse_paper_task (11步)    │   │      ↓ apps/study              │
│ 3. AI 两阶段解析                                    │   │ 10. 作答→判分→记 attempt       │
│    · 阶段1 qwen3.6-plus: 定位每题 bbox             │   │      ↓ answer_views            │
│    · 阶段2 qwen3-vl-plus: 结构化解析                │   │ 11. 答错 → 自动入错题本         │
│      ↓                                              │   │      ↓ apps/wrongbook          │
│ 4. 后处理: 跨页合并/题型规整/答案分离/公式校验/补图   │   │ 12. AI 苏格拉底式引导(B/C模式) │
│      ↓                                              │   │      ↓ guidance_views          │
│ 5. 裁剪插图 + 入库 ExamQuestion(need_review)       │   │ 13. 变式题/掌握度/成长报告     │
│      ↓ parser 完成                                  │   └───────────────────────────────┘
│ 6. 教师审核 review: 确认/编辑/重裁图/驳回重解析      │
│    + 可选 AI 复核(6步pipeline 填充 a/b/c 答案)      │
│      ↓ review_status=confirmed                     │
│ 7. 教师组题建任务 → 发布到班级 missions            │
└──────────────────────────────────────────────────┘
```

---

## 3. 核心流水线 A：试卷解析（`apps/parser`）⭐

系统「发动机」。入口 `POST /api/v1/papers/upload/` → 建 `ExamPaper`(uploaded) + `ParseTask`(pending) → 触发 Celery `parse_paper_task`。**全异步**，进度可轮询 `papers/<id>/parse-progress/`。

### 3.1 11 步流水线

| 步 | 进度 | 动作 | 模块 | 文件 |
|---|---|---|---|---|
| 1 | 5% | Word→PDF（LibreOffice） | `convert_service.word_to_pdf` | `services/convert_service.py` |
| 2 | 18% | Word 预处理：题号顺序/大题标题/内嵌图片/图片引用 | `WordPreprocessor` | `services/word_preprocess_service.py` |
| 3 | 22% | PDF→低DPI图(100DPI) | `convert_service.pdf_to_images` | `services/convert_service.py` |
| 4 | 30% | **阶段1 AI 定位**（qwen3.6-plus，逐页找 bbox/跨页标记） | `position_service.detect_positions` | `services/position_service.py` |
| 5 | 45% | PDF→高DPI图(300DPI) | 同步骤3 | — |
| 6 | 50% | 保存 `ExamPage` + `AIParseResult` | — | `tasks.py` |
| 7 | 50-80% | **阶段2 AI 结构化解析**（qwen3-vl-plus，逐题出题干/选项/答案/解析/知识点/难度/置信度） | `question_parse_service.parse_questions_stage2` | `services/question_parse_service.py` |
| 8 | 82% | **后处理**：跨页合并/题型规整/答案分离/图片缺失校验/LaTeX公式校验/Word补图/题号修正 | `postprocess_service.postprocess_questions` | `services/postprocess_service.py` |
| 9 | 90% | 裁剪插图（PIL 按 bbox 裁高DPI图） | `save_service.crop_question_image` | `services/save_service.py` |
| 10 | 95% | 入库：`ExamQuestion`(自动编码) + `QuestionOption` + `QuestionImage` | `save_service.save_questions` | `services/save_service.py` |
| 11 | 100% | 试卷置 `reviewing`，任务置 `success` | — | `tasks.py` |

### 3.2 两阶段 AI 设计

- **阶段1（定位）**：用便宜的文本模型 qwen3.6-plus 只做题目位置检测，输出 `question_no / section_title / bbox / page_end / is_cross_page`。Prompt：`prompts/position_prompt.py`，Schema：`schemas/page_parse_schema.py`。
- **阶段2（解析）**：用视觉模型 qwen3-vl-plus 对定位区域深度解析，输出完整题目结构。Prompt：`prompts/question_parse_prompt.py`。
- **JSON 修复与校验**：`schema_service.validate_and_repair_json` → `common/utils.repair_json_string` 去脏 → Pydantic 校验，失败降级返回原始数据并告警。

**设计意图**：阶段1降本（只定位），阶段2保质（只对定位区深度解析）。

### 3.3 落库核心表（`apps/parser/models.py`）

- `ExamPaper`：试卷，状态机 `uploaded→converting→converted→parsing→postprocessing→cropping→reviewing→finished/failed`
- `ExamPage`：每页图片记录（低/高DPI 路径、宽高、parse_status）
- `AIParseResult`：AI 调用的原始请求/响应/延迟，用于调试与合规
- `ExamQuestion`：题目主体，含一票 `ai_*` 字段（`ai_probe_result / ai_vision_extract / ai_answer_a/b/c / ai_verifier_result / ai_knowledge_enrichment / ai_processing_status`）供后续审核复核填充
- `QuestionOption`：选项；`QuestionImage`：裁剪插图

### 3.4 容错与重试

- 主任务 `max_retries=2`；支持**断点续传**（跳过已解析题号）
- Beat 定时任务 `periodic_stale_task_check`：15 分钟未完成标记失败
- **单题重解析** `reparse_question_task`、**单页重解析** `reparse_page_task`：只重跑阶段2 或阶段1+2，用于局部修正

---

## 4. 核心流水线 B：教师审核编辑（`apps/review`）

解析完的题目默认 `review_status='need_review'`、`need_review=True`，**必须经教师审核才能进入题库**。这是质量控制闸门。

### 4.1 状态机（`apps/common/status.py`）

```
auto_parsed / need_review ──确认──> confirmed（进入题库）
                     ├──编辑──> modified
                     └──驳回──> rejected（needs_reparse，重跑阶段2）
```

### 4.2 四类操作

1. **审核 CRUD**（`apps/review/views.py`）：试卷列表、题目列表（按 `?status=` 过滤）、`confirm/`、`reject/`、`update/`、`delete/`。
2. **AI 复核**（`services/ai_review_service.py` + Celery）：教师对单题/批量触发 `ai-process/`，跑 `AIReviewService.process_question_full_v2()` 的 **6 步 pipeline**（`apps/common/ai_service.py`）：
   - `Probe`（探查规范化，flash）→ `Vision`（视觉抽取，plus）→ `Solver A`（主解）/ `Solver B`（递进选择）/ `Solver C`（开放引导）→ `Verifier`（校验，flash）
   - 结果写入 `ai_answer_a/b/c` 等。**a/b/c 三套答案正是学生在 B/C 模式引导时看到的内容来源**。
   - 批量处理走 `apps/common/batch_tasks.py`（线程池，并发上限 3，进度/取消标志存 Redis）。
3. **图片重裁剪**（`services/image_recrop_service.py`）：教师在 htmx 校正面板框选新 bbox → 从高DPI原图重新裁剪 → 更新/新增 `QuestionImage`。⚠️ **此服务直接用传入的像素坐标，不做缩放换算**——若前端图有 CSS transform 缩放，坐标必须前端算好再传。
4. **题目编辑**（`services/question_edit_service.py`）：可改 stem/answer/analysis/solution/knowledge_points/difficulty/question_type/选项，改完自动联动 `need_review` 与 `parse_status`。

### 4.3 双形态 API

`apps/review/urls.py`（给 uniapp 的 JSON REST）与 `apps/review/htmx_urls.py`（给 Django 后台的 htmx 端点）两套并行。

---

## 5. 核心流水线 C：学生学习闭环（`apps/study` + `apps/wrongbook`）

```
学生作答 → answer_views._handle_submit_answer
          ├─ _check_answer: 客观题比选项；主观题返回 False（待 AI/人工）
          ├─ 写 AnswerAttempt（attempt_no / is_correct / score / source）
          ├─ 更新 StudentLevelProgress（attempt_count++，答对 pass_score=100）
          └─ 答错 → WrongBookItem.get_or_create（status=not_reviewed）
                        ↓
          wrongbook: 错题列表/详情/变式题推荐（同学科同难度）/掌握度 MasteryRecord
                        ↓
          guidance: 启动会话(B/C模式) → reply → 记 content_log → C 连续2次无效输入自动降级 B
```

### 5.1 关键现状（重要缺口）

学习侧的 AI 苏格拉底引导（`apps/study/guidance_views.py`）**目前未接入真实 LLM**：
- B 模式提示取自审核阶段预存的 `ai_answer_b`
- C 模式问题是硬编码字符串
- `feedback_engine.py` 只返回固定激励语

这是后续接入真实 AI 的明确切入点。

---

## 6. 支撑子系统

| 子系统 | 核心模型/流程 | 文件 |
|---|---|---|
| **认证** | 手机号+短信验证码登录（非密码）；JWT（access 24h / refresh 30d）；`OptionalJWTAuthentication` 允许匿名访问开放端点 | `apps/accounts/{views,auth,services,sms_service}.py` |
| **机构/班级** | `Institution→Class→ClassStudent/ClassTeacher`；三层权限 `IsPlatformAdmin/IsInstitutionAdmin/IsClassTeacher`；入班两种：邀请码直进 或 申请-审批 | `apps/institutions/{models,permissions,request_views,student_views}.py` |
| **知识树** | 学科→学段→年级→学期→章节→知识点的多维树，作为题目元数据标签与教师筛题依据 | `apps/knowledge/{models,teacher_api_views}.py` |
| **任务** | `LearningMission→MissionLevel(5种关卡类型)→MissionQuestionRel`；`draft→published`，支持克隆。⚠️ **任务→班级/学生的派发中间表当前缺失**，发布后无自动派发逻辑 | `apps/missions/` |
| **试卷** | 解析任务的编排层：上传/开始/停止/重解析/进度/删除(软删)；信号自动生成 paper_code | `apps/papers/{views,signals}.py` |

---

## 7. 异步与基础设施

- **Celery**（`config/celery.py`）：`autodiscover_tasks` 自动发现各 app 的 `tasks.py`。
  - 任务：`parse_paper_task`、`reparse_question/page_task`、`single/batch_ai_process_question`、`periodic_stale_task_check`（Beat，5min）。
- **全局异常**（`apps/common/exceptions.py`）：`AIRequestError / SchemaValidationError / ConversionError / TaskExecutionError / ImageCropError`。
- **状态码**（`apps/common/status.py`）：试卷/解析任务/页面/题目四套状态枚举 + 题型枚举。
- **工具**（`apps/common/utils.py`）：`repair_json_string`（修 AI 脏 JSON）、`expand_bbox`、`generate_task_id`；`codegen.py` 生成 paper_code(M90001)/question system_id(M00001)。
- **OSS**（`apps/common/oss_service.py`）：`upload_crop_image` / `upload_crop_image_safe`（失败返 None 不抛）。

---

## 8. 前端（uniapp）流程对应

- **路由**（`uniapp/src/pages.json`）：登录统一入口 → 按角色 `reLaunch`：教师→`workbench`、学生→tabBar(home/wrongbook/growth)、管理员→`admin/home`。
- **请求**（`uniapp/src/utils/request.ts`）：自动带 `Authorization: Bearer`，401 清 token 跳登录；7 天本地免登。
- **教师主线**：`photo-upload`/`import`（上传导入）→ 轮询解析进度 → `review-list` → `question-edit`（编辑/裁图/确认）→ `bank`（题库）→ `mission-create`（组任务发布）→ `class-detail`（管班）。
- **学生主线**：`join-class` → `mission` → `answer`（作答）→ `guidance`（AI引导）→ `wrongbook`/`growth`。
- API 客户端在 `uniapp/src/api/`，与后端 `/api/v1/*` 端点一一对应。

---

## 9. 已知现状缺口（非 bug，未完成功能）

1. **学习侧 AI 引导未接真实 LLM**：`apps/study/guidance_views.py` 的 B/C 模式用的是预存/硬编码内容。
2. **任务派发未落地**：`apps/missions` 发布任务后，缺到班级/学生的派发中间表与逻辑。
3. **裁图坐标无缩放换算**：`apps/review/services/image_recrop_service.py` 直接用像素坐标，前端图若有 transform 缩放需前端预先换算。

---

## 10. 关键文件速查

| 关注点 | 文件 |
|---|---|
| 解析主任务 | `apps/parser/tasks.py` |
| AI 两阶段调用 | `apps/parser/services/{position,question_parse,qwen_text,qwen_vl}_service.py` |
| 后处理/合并/公式 | `apps/parser/services/{postprocess,merge,formula}_service.py` |
| AI 复核 6 步 pipeline | `apps/common/ai_service.py`、`apps/common/ai_prompts.py` |
| 审核状态机 | `apps/review/views.py`、`apps/common/status.py` |
| 图片重裁 | `apps/review/services/image_recrop_service.py` |
| 答题/判分/错题入口 | `apps/study/answer_views.py` |
| AI 引导（未接 LLM） | `apps/study/guidance_views.py`、`apps/study/feedback_engine.py` |
| 认证/短信 | `apps/accounts/{views,auth,services,sms_service}.py` |
| 配置总览 | `config/settings.py` |
