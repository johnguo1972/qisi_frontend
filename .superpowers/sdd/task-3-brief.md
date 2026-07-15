# Task 3: Celery 异步变式题任务 + AI 服务 + 校验器

**位置**: `apps/courses/` 新增 ai_service.py, validator.py, prompts.py, tasks.py

## 新建文件

### 1. `apps/courses/prompts.py`
- `VARIANT_SYSTEM_PROMPT` — 固定 System Prompt（变式题生成，用于上下文缓存）
- `VERIFIER_SYSTEM_PROMPT` — DeepSeek 验证 Prompt
- `build_variant_user_prompt(question_data, variant_mode)` — 构建动态 User Prompt

### 2. `apps/courses/validator.py`
- `VariantValidator` 类，`validate(variant_json, original_question) -> list` 方法
- 校验项：JSON schema, question_type, answer_count, units, value_ranges, single_choice_uniqueness
- 返回空列表 = 通过

### 3. `apps/courses/ai_service.py`
- `QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"`
- `get_api_key()` — 从环境变量 `QWEN_API_KEY` 获取
- `call_ai(system_prompt, user_prompt, model, max_tokens=8000, temperature=0.1) -> str` — 带重试（3次，延迟 5/8/10 秒）
- `parse_json_response(text) -> dict` — 解析 JSON，处理 markdown 代码块

### 4. `apps/courses/tasks.py`
- `generate_variant_task(self, question_id, variant_mode, tree_node_id=None)` — Celery 异步任务
  - 步骤：获取原题 → 创建 VariantTask → 完整性检查 → qwen3.7-plus 生成 → 程序校验 → deepseek 验证 → 保存 ExamQuestion(review_status='need_review')
  - 校验失败或验证不通过时重试一次（self.retry）
- `batch_generate_variants_task(self, question_ids, variant_mode, tree_node_id=None)` — 批量分发

### 修改文件
- `.env` — 新增 AI 模型配置：
  ```
  AI_MODEL_QWEN_37_FLASH=qwen3.7-flash
  AI_MODEL_QWEN_37_PLUS=qwen3.7-plus
  DEEPSEEK_MODEL=deepseek-v4-pro
  ```

## 参考现有代码
- `apps/common/ai_service.py` — AI 调用模式（httpx, 重试逻辑）
- `apps/parser/tasks.py` — Celery 任务模式（@shared_task, bind=True, max_retries）
- `apps/review/views.py` — ExamQuestion 结构

## 约束
- 仅修改 ./front 目录
- AI 服务复用同一 QWEN_API_KEY 和 URL
- Celery 使用 shared_task（与现有 parser/tasks.py 一致）
