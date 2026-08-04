# 删除试卷解析功能设计

## 背景与根因

当前 Word/PDF 试卷导入会创建 `ParseTask`，随后直接调用或向 Celery 投递
`apps.parser.tasks.parse_paper_task`。失败任务还会被 Celery Beat 每 5 分钟执行的
`periodic_stale_task_check` 再次投递。因此，只停止某个 Worker 或隐藏一个前端按钮，
都不能阻止试卷解析继续发生。

已确认的完整试卷解析触发入口包括：

1. `POST /api/v1/questions/import-batches`：教师上传 Word/PDF 后自动解析；
2. `POST /api/v1/papers/<paper_id>/parse/`：开始完整解析；
3. `POST /api/v1/papers/<paper_id>/reparse/`：重新完整解析；
4. Review HTMX 的试卷上传和重新解析入口；
5. Celery Beat 对超时 `full_parse`/`page_reparse` 任务的自动恢复；
6. Review HTMX 的单题重新解析入口；
7. Redis broker 中部署前已经排队的解析任务。

## 方案比较

### 方案 A：完整移除文档解析流水线（采用）

删除完整试卷解析、单页重解析、单题重解析任务及所有生产触发入口，移除定时恢复，
同时保留题目/试卷数据模型和仍被其他功能复用的文件转换、图片裁剪能力。

优点：符合“现在不需要此功能”的要求；不会继续产生后台错误和 AI 费用；不破坏现有题库数据。
缺点：Word/PDF 上传后自动生成题目的能力不再可用。

### 方案 B：保留任务名但改为空操作

类似历史自动 AI 任务的兼容墓碑，只禁用执行，不删除代码和接口。

优点：旧队列消息不会报未注册任务。
缺点：不符合明确的删除要求；入口、状态和维护负担仍然存在。

### 方案 C：删除整个 `apps.parser` 应用及数据库表

连同 `ExamQuestion`、`ExamPage`、`QuestionImage` 等模型一起删除。

优点：删除最彻底。
缺点：会破坏题库、课程、任务、错题本、拍照建题和手工 AI 等核心功能，不可采用。

## 删除边界

### 删除

- `apps.parser.tasks` 中的：
  - `parse_paper_task` / `_run_parse_paper_task`
  - `reparse_page_task` / `_run_reparse_page_task`
  - `reparse_question_task` / `_run_reparse_question_task`
  - `periodic_stale_task_check`
  - 仅服务于上述流水线的辅助函数
- `config.settings.CELERY_BEAT_SCHEDULE` 中的解析超时恢复任务。
- `apps.papers` 中上传、开始解析、停止解析、重新解析、解析进度接口；保留已有试卷删除能力。
- `apps.study.import_views` 的 Word/PDF 导入批次及其路由。
- Review HTMX 中试卷上传、进度、重新解析和单题重新解析入口；保留只读试卷/题目审核入口。
- UniApp 教师端 Word/PDF 试卷解析页面、菜单入口、解析 API、轮询和相关 E2E/契约测试。
- 仅被已删除流水线使用的 position、question parse、postprocess、merge、formula、schema、Word 预处理模块及提示词/Schema。
- 只验证已删除功能的测试。
- 本地 Redis broker 中已排队的三类解析任务消息。

### 保留

- `ExamPaper`、`ParseTask`、`ExamPage`、`ExamQuestion`、`QuestionOption`、`QuestionImage`、
  `AIParseResult` 模型、迁移和历史数据；不执行删表或数据迁移。
- JSON 题库包导入和大压缩包导入。
- 手工创建题目、拍照建题、题库维护、课程材料导入、审核、错题本和手工 AI 处理。
- `convert_service`：课程材料导入仍使用 Word/PDF 转图片能力。
- `save_service.crop_question_image`：图片重新裁剪仍在使用；仅移除其中只为解析流水线服务的保存函数。
- Review HTMX 的试卷列表、试卷详情和现有题目查看能力，但不再显示解析进度或解析操作。
- `ExamPaper` 删除接口；删除时不再因历史 `running` 解析任务而阻塞。

## 删除后的数据流

1. 教师端不再显示“上传试卷解析”页面和菜单入口。
2. Word/PDF 解析 API 返回 404（路由不存在），系统不会创建新的 `full_parse`、
   `page_reparse` 或 `question_reparse` 任务。
3. Celery Beat 不再扫描或重新投递解析任务。
4. Celery Worker 不再注册三类解析任务。
5. 已有题目和试卷仍可浏览、编辑、审核、删除并用于课程/任务。
6. 题目新增改走手工创建、拍照建题或 JSON/ZIP 数据导入。

## 队列清理顺序

为避免删除任务注册后 Worker 收到旧消息并报告 “unregistered task”，实施时按以下顺序操作：

1. 停止或确认本地 Celery Worker 未消费；
2. 统计 broker 中各任务名数量；
3. 原子移出且仅移出以下任务消息，保留其他队列消息和顺序：
   - `apps.parser.tasks.parse_paper_task`
   - `apps.parser.tasks.reparse_page_task`
   - `apps.parser.tasks.reparse_question_task`
4. 将移出的消息放入 24 小时自动过期的隔离队列；
5. 验证活动队列中三类消息均为 0；
6. 再删除任务代码和 Beat 配置。

## 兼容与错误处理

- 不删除数据库历史 `ParseTask`，避免影响序列化及旧记录读取。
- 现存 `running`/`pending` 解析记录不再自动重试；实现时统一标记为 `cancelled`，
  错误说明为“试卷解析功能已停用”。
- 所有前端入口与 API helper 同步删除，避免用户点击后收到 404。
- 不修改公共 AI 组件、A/B/C、AI 探查和 DeepSeek 校验链路。

## 测试与验收

1. 静态契约测试证明生产代码中不存在三个 Celery 任务名、`.delay()` 调用或 Beat 调度。
2. URL 反向解析/请求测试证明完整解析、重解析、停止和进度接口均已移除。
3. 菜单和 UniApp 源码测试证明不再展示试卷解析入口或轮询。
4. JSON 导入、手工建题、拍照建题、审核图片裁剪和课程材料转换的回归测试通过。
5. `python manage.py check` 通过。
6. AI/review 既有回归测试通过。
7. UniApp H5 构建通过。
8. Redis 活动队列中三类解析任务数量均为 0。

不把真实 AI 调用或浏览器端到端验证表述为已完成，除非实际执行并取得数据承载证据。
