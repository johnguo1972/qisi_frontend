# Task 3 Report: Celery 异步变式题任务 + AI 服务 + 校验器

**Status:** DONE
**Date:** 2026-07-15
**Branch:** feature/task-1-courses-app
**Commit:** 395811d feat(courses): Celery 异步变式题任务 + AI 服务 + 校验器

## 创建的文件

| 文件 | 说明 |
|------|------|
| `apps/courses/prompts.py` | 变式题生成 System Prompt + 校验器 System Prompt + 动态 User Prompt 构建函数 |
| `apps/courses/ai_service.py` | Qwen + DeepSeek AI 调用服务（3 次重试，延迟 5/8/10s，JSON 解析含 markdown 清理） |
| `apps/courses/validator.py` | VariantValidator 校验器类（7 个校验维度） |
| `apps/courses/tasks.py` | Celery 异步任务：单题生成 + 批量分发 |
| `apps/courses/tests/test_validator.py` | 21 个单元测试 |

## 修改的文件

| 文件 | 说明 |
|------|------|
| `.env` | 新增 AI_MODEL_QWEN_37_FLASH, AI_MODEL_QWEN_37_PLUS, DEEPSEEK_API_KEY, DEEPSEEK_MODEL |

## 测试摘要

```
Ran 21 tests in 0.307s — OK
```

| 测试类 | 覆盖维度 | 数量 |
|--------|----------|------|
| TestVariantValidatorSchema | JSON schema 完整性（必填字段/选项存在性） | 5 |
| TestVariantValidatorQuestionType | 题型合法性 | 2 |
| TestVariantValidatorAnswerCount | 答案数量匹配/选项数量 | 5 |
| TestVariantValidatorSingleChoiceUniqueness | 单选题选项唯一性 | 2 |
| TestVariantValidatorValueRanges | 难度范围 1-5 | 3 |
| TestVariantValidatorStemEmpty | 题干非空 | 2 |
| TestVariantValidatorNotIdentical | 变式题与原题不相同 | 2 |

## 架构设计

### 变式题生成流程

```
原题 ExamQuestion
  → build_question_data()
  → 创建 VariantTask(status='running')
  → 完整性检查
  → call_ai(qwen3.7-plus, VARIANT_SYSTEM_PROMPT, user_prompt)
  → parse_json_response()
  → VariantValidator.validate()
    → 校验失败 → self.retry(countdown=15)
  → call_ai(deepseek-v4-pro, VERIFIER_SYSTEM_PROMPT, verifier_prompt)
    → 校验不通过 → self.retry(countdown=15)
  → _save_variant_as_question() → ExamQuestion(review_status='need_review')
  → VariantTask(status='success')
```

### Celery 任务

- `generate_variant_task(question_id, variant_mode, tree_node_id)` — 单题生成（bind=True, max_retries=2）
- `batch_generate_variants_task(question_ids, variant_mode, tree_node_id)` — 批量分发

## 校验维度

1. **JSON schema** — 必填字段 stem, question_type, answer 存在
2. **question_type** — 合法题型（单/多选、填空、简答、计算、证明等）
3. **answer_count** — 单选单字母、多选多字母（2+）、选项数量≥2
4. **single_choice_uniqueness** — 选项内容互不相同
5. **value_ranges** — 难度 1-5
6. **stem_not_empty** — 题干非空
7. **not_identical** — 变式题与原题不完全相同

## 注意事项

- DeepSeek API Key 未配置时自动跳过 AI 校验（不阻塞流程）
- Celery 重试时指数退避：首次 15s，二次 30s
- 生成的题目 review_status='need_review'，需人工审核
- 所有 AI 调用复用同一 QWEN_API_KEY，DeepSeek 使用独立的 DEEPSEEK_API_KEY
