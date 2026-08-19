# 无答案题目 AI 仲裁设计

## 目标

当题库题目的 `answer` 为空或仅包含空白时，先由 DeepSeek 思考模式建立可持久化的标准答案与解析，再以该答案作为 A、B、C 模式的唯一答案基准。不同教学模式的步骤、问题和解释不参与跨模型一致性比较。

## 范围与判定

- 仅 `answer` 为空白的题目进入本设计；已有非空 `answer` 的题目继续使用现有仲裁策略。
- `analysis` 即使已有内容，也不能替代答案基准；它作为 DeepSeek 独立解题的参考资料输入，并允许 DeepSeek 用新解析覆盖。
- 所有模型输入继续使用 `QuestionContextBuilder` 构建的完整题目上下文，包含题干、选项、图片 URL、视觉结果、题型、学科、已有解析和 AI 探查结果。

## 数据流

```text
AI 探查
  -> 立即保存 ai_probe_result
DeepSeek 独立解题（思考模式）
  -> 输出 canonical_answer / canonical_analysis / confidence
  -> 立即保存 ExamQuestion.answer / ExamQuestion.analysis / ai_verifier_result
每个模式 A、B、C：
  Qwen 生成该模式内容
  -> 规范化 final_answer 与 canonical_answer 比较
  -> 一致且模式 Schema 有效：立即保存该模式
  -> 不一致：DeepSeek 最终复核当前模式内容
       -> 复核认可 Qwen：立即保存
       -> 复核否决：只重试该模式 Qwen 一次
            -> 再次比较和复核
            -> 仍否决：保存安全错误码，继续下一模式
```

## DeepSeek 基准解答契约

基准解答由专用 `DeepSeekBaselineSolveComponent` 调用；它使用 DeepSeek 思考模式，但不要求、也不生成 A/B/C 的模式内容。新增严格响应 Schema：

- `canonical_answer`：非空、可规范化的最终答案；
- `canonical_analysis`：非空的简明解析；
- `confidence`：`0` 到 `1` 的数值；
- `key_facts`：非空事实数组；
- `context_hash`：由服务层写入，绑定题目上下文。

任何缺失、不可规范化或低于 `0.80` 的基准解答均不写入题目答案；该题记录 `baseline_invalid` 并继续下一题。

## 模式核对与重试

- Qwen 模式输出先经过现有模式 Schema 验证。
- 仅比较 `final_answer` 与持久化的 `canonical_answer`；不比较过程、问题序列、解析文案或模式特有字段。
- 首次不一致时，DeepSeek 最终复核接收：完整题目上下文、基准答案与解析、当前模式 Qwen 输出、目标模式 Schema。它只返回是否认可当前模式答案及必要的完整模式替代内容。
- 复核否决后，仅重跑一次同一模式的 Qwen；第二轮仍不被复核认可时，将该模式保存为失败，错误码为 `mode_<x>_answer_mismatch_after_retry`。
- 一致、被认可或由 DeepSeek 提供合格替代模式内容时，立即保存该模式结果。

## 持久化和失败安全性

- 探查、基准答案解析、A、B、C 每一步成功后立即写入；后续失败不得回滚前一步。
- `ai_verifier_result` 仅保存安全的基准事实、置信度和上下文哈希，不保存思考链、原始模型响应或密钥。
- 任务日志及 API 仅暴露枚举分类，例如 `rate_limited`、`connect_timeout`、`read_timeout`、`schema_invalid`、`provider_unavailable`、`baseline_invalid`、`answer_mismatch_after_retry`。
- 单独 B 模式仍必须复用已保存的 `ai_probe_result`；没有探查结果时返回 `probe_result_required`，不得隐式重新探查。

## 验收标准

1. 无答案题在 DeepSeek 基准解答成功后立即持久化 `answer` 和 `analysis`。
2. A/B/C 的过程差异不会导致仲裁失败；只要最终答案等于基准答案且 Schema 合格，即保存 Qwen 输出。
3. 不一致仅对当前模式调用最终复核，并且最多重跑一次该模式。
4. 第二轮仍不一致时，其他模式和其他题继续运行，且失败原因可统计。
5. 已有答案题和单独 B 模式的既有兼容性测试保持通过。
