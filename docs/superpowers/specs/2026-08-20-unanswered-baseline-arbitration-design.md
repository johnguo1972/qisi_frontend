# 无答案题 AI 仲裁设计

## 目标

无原始答案的题目必须先获得并持久化 DeepSeek 标准答案与解析；后续 A/B/C 仅以最终答案与该基线比较，教学过程不参与一致性判定。

## 数据流

1. 探查完成后，若题目没有原始答案且没有有效 `unanswered_baseline`，调用 DeepSeek 思考模式生成 `canonical_answer` 与 `canonical_analysis`。
2. 基线成功后立即单独保存 `answer`、`analysis` 和 `ai_verifier_result.unanswered_baseline`；后续任何模式失败都不得回滚基线。
3. A/B/C 生成时复用该基线。Qwen 最终答案相同即采用；不同时才调用 DeepSeek 最终复核。
4. 最终复核不能采用时，重试该模式一次；第二次仍失败时保存脱敏错误并继续下一题。

## 单模式任务

单独 A/B/C 任务必须通过同一基线入口。无答案题的 B 模式不可走普通的 `solve_mode_with_arbitration`，而必须走 `solve_unanswered_mode_with_arbitration`。

## 失败可观测性

保存脱敏的模式、阶段、提供商、错误类别、尝试次数和 Schema 字段路径。不得保存 API Key、完整提示词或原始模型响应。

## 并发

本地和生产环境均限制为 6 路：Celery worker、全局题目租约、Qwen 和 DeepSeek 提供商租约均不得超过 6。
