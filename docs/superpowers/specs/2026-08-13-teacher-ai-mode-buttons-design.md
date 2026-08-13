# 教师题库 A/B/C AI 模式按钮设计

## 目标

在教师端题库管理右侧操作栏中，于现有“AI-A模式”下方依次增加“AI-B模式”和“AI-C模式”。三个按钮均只在用户手工点击后，对当前勾选题目提交对应的单模式 AI 任务。

## 交互与调用

- 操作栏按 `AI探索`、`AI-A模式`、`AI-B模式`、`AI-C模式` 排列。
- `RightActionPanel` 分别发出 `ai-mode-a`、`ai-mode-b`、`ai-mode-c` 事件。
- 题库页面以公共 `handleAiMode(mode: 'A' | 'B' | 'C')` 处理三个事件。
- 对每个已选题目调用现有 `questionApi.aiProcessMode(questionId, mode)`。
- 未选题目时不发请求并提示“请先选择题目”。
- 全部提交成功时显示对应模式成功提示；任一提交拒绝时显示对应模式失败提示。
- 不调用批量完整 AI 管线，不自动触发其他模式。

## 后端与数据

沿用 `/review/question/{questionId}/ai-process-mode/{mode}/` 和 `single_mode_ai_process_question`。A、B、C 分别写入 `ai_answer_a`、`ai_answer_b`、`ai_answer_c`，不新增接口和数据库迁移。

## 验证

- 可执行前端行为测试覆盖按钮事件、A/B/C 参数、多题提交、空选择和失败提示。
- 后端契约测试覆盖 A/B/C 独立任务路由与字段写入。
- H5 构建通过。
- 对指定题目 `019fa8a0-9397-7101-8180-545551f3f33f` 进行 A/B/C 三次真实调用，确认三个字段各自落库且模式、模型、时间信息有效。

