# Celery 无效题目 AI 任务修复设计

## 背景

`single_generate_ai_answers` 收到的部分 `ExamQuestion` ID 在当前数据库中不存在。任务在查询题目时抛出 `ExamQuestion.DoesNotExist`，但现有异常处理会把它当作临时故障进行指数退避重试，造成重复错误日志。

当前 `ExamQuestion` 的 `post_save` 信号还会在数据库事务提交前直接发送 Celery 任务。Worker 可能早于事务提交读取题目；如果事务最终回滚，队列中还会留下永远无法成功的任务。

## 目标

- 仅在创建或更新题目的数据库事务成功提交后发送自动 AI 任务。
- 对已经删除、回滚或来自陈旧队列的题目任务安全跳过，不执行 AI 调用，也不重试。
- 保持正常 AI 任务及临时 AI 服务错误的现有重试行为不变。
- 不清空 Redis/Celery 队列，不修改 `./front` 之外的代码。

## 非目标

- 不调整 AI 模型、提示词、API 地址或模型路由。
- 不改变批量 AI 任务的进度数据结构。
- 不处理或删除当前工作树中的其他未提交文件。

## 设计

### 事务提交后入队

`apps/study/receivers.py` 中的 `auto_trigger_ai_generation` 保留现有触发条件，但通过 `transaction.on_commit` 注册入队回调。回调只捕获不可变的题目 ID，避免闭包引用可变模型实例。

数据流变为：

1. `ExamQuestion.save()` 触发 `post_save`。
2. 信号判断题目已自动解析且尚无 A 模式答案。
3. 信号注册事务提交回调，不立即发送任务。
4. 事务成功提交后调用 `single_generate_ai_answers.delay(question_id)`。
5. 事务回滚时 Django 丢弃回调，不产生无效任务。

### 不存在题目直接跳过

`apps/common/batch_tasks.py` 中的单题任务在创建 AI 服务前查询题目是否存在。不存在时记录 warning，并返回：

```python
{
    "status": "skipped",
    "question_id": "<题目 ID>",
    "reason": "question_not_found",
}
```

该分支不创建 AI 服务、不调用模型、不写题目，也不调用 `self.retry`。预检后题目仍可能被并发删除，因此任务还会单独捕获后续阶段抛出的 `ExamQuestion.DoesNotExist`，使用相同结果安全结束。

其他异常继续沿用现有指数退避重试，确保临时网络、模型服务及数据库错误不会被误判为永久错误。

## 测试策略

采用测试驱动方式完成：

1. 信号测试证明事务提交前不会调用 `.delay()`，提交后只调用一次。
2. 信号测试证明事务回滚不会调用 `.delay()`。
3. 任务测试证明题目不存在时返回 `skipped`，不创建 AI 服务且不调用 retry。
4. 保留并运行现有正常题目任务兼容性测试，确认成功结果与公共 AI 组件调用参数不变。
5. 运行相关应用测试和 `manage.py check`，检查回归与 Django 配置。

## 运行与兼容性

部署代码后需要重启 Django/Celery Worker 才会加载新逻辑。旧队列中的无效任务无需清空；加载新代码的 Worker 会将其标记为跳过。返回值只新增无效任务的 `skipped` 状态，正常任务仍返回原有 `success` 状态。
