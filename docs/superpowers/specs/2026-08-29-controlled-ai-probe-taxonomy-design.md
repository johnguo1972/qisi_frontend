# 三级受控 AI 探查与知识点目录设计

## 目标

将现有“AI 自由输出知识点名称，再尝试匹配本地知识树”的流程，替换为最多三次的受控候选选择流程。AI 只能从本地目录提供的主题、子主题和知识点候选中选择标准 ID，避免产生无法进入题库知识树的自由文本知识点。

探查完成后，系统必须持久化题目的学科、学段、题型、难度级别、具体难度值、知识点、年级、学期和章节；其中年级、学期、章节由最后一个有效知识点反推。

## 非目标

- 不改变 A、B、C 三种答案生成与仲裁逻辑。
- 不修改由外部维护的 `knowledge_points` 表结构。
- 不以字符串模糊匹配作为正式知识点绑定的依据。

## 目录数据模型

新增本系统维护的目录数据，和现有 `knowledge_points` 表分离：

```text
KnowledgeTopic
├─ id
├─ subject                 # math / physics
├─ stage                   # junior / senior
├─ parent                  # 空为一级主题，否则为子主题
├─ name
├─ sort_order
├─ is_enabled
└─ catalog_version

KnowledgeTopicPoint
├─ id
├─ topic
├─ knowledge_point_id      # 字符串，兼容现有 UUID 与历史 ID
├─ sort_order
└─ is_enabled
```

一级主题示例：初中物理的力学、热学、声学、光学、电学。主题可包含子主题；叶子主题关联一到多个本地标准知识点。

一个主题下最终可供 AI 选择的知识点超过 30 个时，必须继续细分子主题。主题目录变更时递增 `catalog_version`。

## 探查调用流程

```text
题干、选项、表格、图片与读图事实
        │
        ▼
调用 1：范围定位
subject + stage + topic_id + question_type + difficulty_level + normalized_text
        │ 立即保存
        ▼
调用 2：子主题定位（仅当一级主题存在子主题时）
subtopic_id
        │ 立即保存；无子主题时跳过
        ▼
调用 3：知识点与难度细化
knowledge_point_ids + difficulty_score + difficulty_reason
        │ 立即保存
        ▼
用最后一个有效知识点反推 grade / semester / chapter
```

调用 1、2、3 均使用 `qwen3.7-flash`。模型只做候选集选择，不生成候选集外的目录名称。

### 调用 1：范围定位

输入包括规范化题面、选项、表格、可用图片/读图结果，以及四个学科-学段范围内的一级主题候选。

输出契约：

```json
{
  "subject": "physics",
  "stage": "junior",
  "topic_id": "junior_physics_thermal",
  "question_type": "single_choice",
  "difficulty_level": "L3",
  "normalized_text": "规范化题干",
  "confidence": 0.91
}
```

`subject`、`stage`、`topic_id` 必须属于输入候选。调用成功后立即写入探查阶段结果、题目学科与题型。

### 调用 2：子主题定位

仅在调用 1 选择的主题存在启用子主题时执行。输入为题面、调用 1 的结果和该主题下的子主题候选；输出为一个 `subtopic_id`。

无子主题时不调用本阶段，直接将调用 1 的主题作为叶子主题。模型不可自行创建子主题。

### 调用 3：知识点与难度细化

输入为题面、已确认的目录路径、叶子主题关联的标准知识点候选，以及调用 1 确定的 `difficulty_level`。

输出契约：

```json
{
  "knowledge_point_ids": ["019fb217-xxxx-xxxx-xxxx-xxxxxxxxxxxx"],
  "difficulty_score": 3.2,
  "difficulty_reason": "知识点关联较多，包含概念判断与综合应用",
  "confidence": 0.88
}
```

约束：

- `knowledge_point_ids` 为 1 到 5 个候选内标准 ID，按相关性排序。
- `difficulty_score` 保留一位小数，整数部分必须与 `difficulty_level` 一致。
- 取值范围为 L1: 1.0-1.9，L2: 2.0-2.9，L3: 3.0-3.9，L4: 4.0-4.9，L5: 5.0-5.9。
- 模型不能返回自由知识点名称或空 ID。

## 数据持久化

新增 `ExamQuestion.difficulty_level`，取值为 `L1` 至 `L5`。保留既有 `ExamQuestion.difficulty` 的 DecimalField，写入具体难度值，例如 `3.20`。

正式知识点仅写入：

```json
[
  {"id": "标准知识点ID", "module": "标准知识点名称"}
]
```

`ai_probe_result` 持久化全部阶段的输入版本、候选目录版本、模型输出、失败信息和完成状态。调用 3 成功后，以 AI 返回顺序的最后一个有效知识点反推并写入：`subject`、`stage`、`grade`、`semester`、`chapter`。

每次调用完成后立即保存；后续调用失败不得清除已完成阶段的数据。

## 校验、重试与缓存

- 后端在每一阶段校验返回 ID 是否属于当次候选集；不属于即视为无效结果。
- JSON/候选集校验失败时，仅对当前阶段执行一次结构修复重试。
- 重试仍失败时保留已完成阶段，记录失败原因，不写入 `id=null` 的正式知识点关联。
- 缓存键包含题目输入哈希、目录路径和 `catalog_version`。题面与目录版本均未改变时，复用已完成阶段。
- 目录版本变化时，仅重新运行受影响的后续阶段。

## 迁移与历史数据

1. 创建主题、子主题和主题-知识点关联表及 `difficulty_level` 字段迁移。
2. 导入并核验初中/高中物理、初中/高中数学的主题树与知识点归属。
3. 对历史题先进行目录受控探查；不重跑 A/B/C 答案。
4. 只有最终标准知识点 ID 全部有效的题目才回写 `ExamQuestion.knowledge_points`。

## 测试与验收

- 单元测试：每次调用的候选集越界拒绝、无子主题跳过第二次、多个知识点顺序与最后节点反推、L3/3.2 和 L5/5.9 约束。
- 集成测试：三级结果逐步保存，后续阶段失败后前序结果保留。
- API 测试：题库知识树计数与按知识点筛选仅使用正式 ID 关联。
- 回归测试：A/B/C 答案生成仍读取已保存的正式知识点引用。
- 生产验收：对“9年级秋季班课件练习”277 道题先抽样运行，再执行全量补齐，核对课程练习与题库管理显示一致。
# 模块粒度修订（2026-08-29）

本文中先前出现的 `KnowledgeTopicPoint`、`knowledge_point_ids` 及“模型选择标准知识点 ID”表述，均由本修订替代：第三阶段仅允许模型从 `knowledge_points.module` 中选择 1-5 个标准模块（当前本地约 470 个去重模块），返回字段为 `knowledge_modules`。模型不直接面对数千条细粒度 `KnowledgePoint` 行。

服务端随后按“科目 + 学段 + 叶子章节 + module”解析每个已选模块的实际树节点 ID，并按既有 `ExamQuestion.knowledge_points = [{"id", "module"}]` 格式写入。因此，题库知识树筛选、统计与历史数据兼容性不变；最后一个已选模块对应节点负责反推年级、学期与章节。
