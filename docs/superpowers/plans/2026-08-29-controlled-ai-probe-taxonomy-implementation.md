# 三级受控 AI 探查 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AI 探查在最多三次受控调用中，从本地主题、子主题和知识点候选中选择标准 ID，并持久化题型、双层难度和知识树反推属性。

**Architecture:** 新增可维护的主题目录与主题-知识点关联表，不修改外部维护的 `knowledge_points` 表。探查第一阶段选择学科、学段与一级主题，第二阶段按需选择子主题，第三阶段选择知识点 ID 并细化难度；每阶段完成即保存，后端拒绝候选集外 ID。

**Tech Stack:** Django 5.2、PostgreSQL、Celery、Pydantic、Qwen `qwen3.7-flash`、pytest、UniApp API 契约。

**Spec:** `docs/superpowers/specs/2026-08-29-controlled-ai-probe-taxonomy-design.md`

## Global Constraints

- 只修改 `./front` 下文件。
- 不修改外部维护的 `knowledge_points` 表结构；其 ID 必须以字符串保存以兼容 UUID 与历史数据。
- AI 模型 URL、密钥只从 `.env` 读取；模型、路由与提示词只从 `config/ai_config.cfg` 读取。
- 三次探查均使用 `qwen3.7-flash`，每阶段候选集越界或 JSON 契约失败时仅重试当前阶段一次。
- 正式 `ExamQuestion.knowledge_points` 只能保存本地标准知识点的 `id` 与 `module`，绝不保存 `id=null`。
- `difficulty_level` 为 `L1` 到 `L5`；`difficulty` 为两位小数，范围 L1:1.0-1.9、L2:2.0-2.9、L3:3.0-3.9、L4:4.0-4.9、L5:5.0-5.9。
- 每一个新增行为都先写失败测试并确认红灯，再写最小实现。

---

## 文件结构与接口边界

| 文件 | 职责 |
|---|---|
| `apps/knowledge/models.py` | 主题树与主题-标准知识点关联模型。 |
| `apps/knowledge/migrations/0002_controlled_probe_topics.py` | 创建系统维护的主题目录表和题目难度级别字段。 |
| `apps/knowledge/controlled_catalog.py` | 读取目录、构造每阶段候选集、校验返回 ID。 |
| `apps/knowledge/management/commands/import_controlled_topic_catalog.py` | 从受版本控制的 JSON 导入主题和关联关系，并验证覆盖率。 |
| `config/controlled_knowledge_topics.json` | 初始主题/子主题/知识点映射的唯一导入源。 |
| `apps/common/ai/schemas.py` | 三阶段严格 Pydantic 响应契约。 |
| `apps/common/ai/components/question_probe.py` | 第一次范围定位组件与后两次受控选择组件。 |
| `apps/common/ai_service.py` | 阶段编排、逐步保存、缓存和最终题目字段回写。 |
| `config/ai_config.cfg` | 三阶段模型任务、路由与候选集提示词。 |
| `apps/review/tasks.py` | 探查完成判定、批量任务与阶段重试兼容。 |
| `apps/study/serializers.py` | 将难度级别与具体难度同时返回给前端。 |
| `apps/common/management/commands/reconcile_controlled_probe_taxonomy.py` | 只补齐探查/正式知识点关联的历史数据命令。 |
| `docs/ai_public_component_flow.md` | 公开 AI 流程、字段与提示词摘要。 |

## Task 1: 主题目录持久化模型与难度级别迁移

**Files:**
- Modify: `apps/knowledge/models.py`
- Create: `apps/knowledge/migrations/0002_controlled_probe_topics.py`
- Modify: `apps/parser/models.py`
- Create: `apps/knowledge/tests/test_controlled_catalog_models.py`

**Interfaces:**
- Produces `KnowledgeTopic(subject, stage, parent, name, sort_order, is_enabled, catalog_version)`。
- Produces `KnowledgeTopicPoint(topic, knowledge_point_id, sort_order, is_enabled)`。
- Produces `ExamQuestion.difficulty_level: CharField(choices=L1..L5, null=True, blank=True)`。

- [ ] **Step 1: 写入失败模型测试**

```python
@pytest.mark.django_db
def test_topic_point_uses_string_knowledge_point_id_and_unique_topic_link():
    topic = KnowledgeTopic.objects.create(
        subject="physics", stage="junior", name="热学", catalog_version=1,
    )
    link = KnowledgeTopicPoint.objects.create(
        topic=topic, knowledge_point_id="019fb217-3a1c-78b0-916b-eebba1736762",
    )
    assert link.knowledge_point_id.startswith("019fb217-")
    with pytest.raises(IntegrityError):
        KnowledgeTopicPoint.objects.create(
            topic=topic, knowledge_point_id=link.knowledge_point_id,
        )


@pytest.mark.django_db
def test_question_keeps_level_and_decimal_difficulty_in_separate_fields(question):
    question.difficulty_level = "L3"
    question.difficulty = Decimal("3.20")
    question.save()
    question.refresh_from_db()
    assert question.difficulty_level == "L3"
    assert question.difficulty == Decimal("3.20")
```

- [ ] **Step 2: 验证红灯**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/knowledge/tests/test_controlled_catalog_models.py -q
```

Expected: FAIL because `KnowledgeTopic`、`KnowledgeTopicPoint` 和 `difficulty_level` 尚不存在。

- [ ] **Step 3: 实现模型和迁移**

在 `apps/knowledge/models.py` 增加受 Django 管理的模型，表名固定为 `knowledge_topic`、`knowledge_topic_point`。`KnowledgeTopic` 使用 UUID 主键、`parent = ForeignKey('self', null=True, blank=True)`；`KnowledgeTopicPoint.knowledge_point_id` 为 `CharField(max_length=64)`，并为 `(topic, knowledge_point_id)` 建唯一约束。

在 `apps/parser/models.py` 为 `ExamQuestion` 增加：

```python
DIFFICULTY_LEVEL_CHOICES = [(f"L{level}", f"L{level}") for level in range(1, 6)]
difficulty_level = models.CharField(
    max_length=2, choices=DIFFICULTY_LEVEL_CHOICES, null=True, blank=True,
)
```

创建迁移：两个新目录表、索引 `(subject, stage, parent, is_enabled)`，以及 `tiku_exam_question.difficulty_level` 可空列。

- [ ] **Step 4: 验证绿灯并检查迁移**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/knowledge/tests/test_controlled_catalog_models.py -q
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' manage.py makemigrations --check
```

Expected: tests PASS；`makemigrations --check` 不生成额外迁移。

- [ ] **Step 5: 提交本任务**

```powershell
git add apps/knowledge/models.py apps/knowledge/migrations/0002_controlled_probe_topics.py apps/parser/models.py apps/knowledge/tests/test_controlled_catalog_models.py
git commit -m "feat: add controlled knowledge topic catalog models"
```

## Task 2: 可导入且可验证的主题目录

**Files:**
- Create: `config/controlled_knowledge_topics.json`
- Create: `apps/knowledge/management/commands/import_controlled_topic_catalog.py`
- Create: `apps/knowledge/tests/test_controlled_catalog_import.py`

**Interfaces:**
- Consumes JSON entries `{id, subject, stage, parent_id, name, sort_order, knowledge_point_ids}`。
- Produces已启用主题树，并拒绝引用不存在本地知识点的条目。
- Returns command summary `{topics, links, uncovered_points, invalid_ids}`。

- [ ] **Step 1: 写入失败导入测试**

```python
@pytest.mark.django_db
def test_import_catalog_rejects_unknown_standard_knowledge_point(tmp_path):
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(json.dumps({"topics": [{
        "id": "junior-physics-thermal",
        "subject": "physics", "stage": "junior", "parent_id": None,
        "name": "热学", "sort_order": 10,
        "knowledge_point_ids": ["unknown-id"],
    }]}), encoding="utf-8")
    with pytest.raises(CommandError, match="unknown standard knowledge point"):
        call_command("import_controlled_topic_catalog", path=str(catalog_file))
```

- [ ] **Step 2: 验证红灯**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/knowledge/tests/test_controlled_catalog_import.py -q
```

Expected: FAIL because导入命令不存在。

- [ ] **Step 3: 实现导入命令与初始目录格式**

创建 JSON 文档，根字段为 `catalog_version` 与 `topics`。每个主题 ID 使用稳定的短横线标识；初中物理至少含力学、热学、声学、光学、电学，且每个叶子主题的 `knowledge_point_ids` 只引用生产 `knowledge_points.id`。

命令应在事务中执行：更新同 ID 主题、替换其关联、验证每一个关联 ID 存在、输出未覆盖的启用知识点数。若任何 ID 无效，回滚整个导入。

- [ ] **Step 4: 验证绿灯及目录覆盖报告**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/knowledge/tests/test_controlled_catalog_import.py -q
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' manage.py import_controlled_topic_catalog --path config/controlled_knowledge_topics.json --dry-run
```

Expected: tests PASS；dry-run 输出四个学科-学段范围内的主题数、关联数和未覆盖知识点数。

- [ ] **Step 5: 提交本任务**

```powershell
git add config/controlled_knowledge_topics.json apps/knowledge/management/commands/import_controlled_topic_catalog.py apps/knowledge/tests/test_controlled_catalog_import.py
git commit -m "feat: add versioned controlled knowledge topic catalog"
```

## Task 3: 候选目录服务与受控 ID 校验

**Files:**
- Create: `apps/knowledge/controlled_catalog.py`
- Create: `apps/knowledge/tests/test_controlled_catalog_service.py`

**Interfaces:**
- `root_topic_candidates() -> list[dict]`
- `child_topic_candidates(topic_id: str) -> list[dict]`
- `leaf_knowledge_candidates(topic_id: str) -> list[dict]`
- `validate_selected_ids(candidate_ids: Iterable[str], selected_ids: Iterable[str], maximum: int = 5) -> list[str]`

- [ ] **Step 1: 写入失败服务测试**

```python
@pytest.mark.django_db
def test_leaf_candidates_are_limited_to_selected_topic_and_keep_standard_ids(topic_tree):
    candidates = leaf_knowledge_candidates(topic_tree.thermal_leaf.id)
    assert candidates == [{
        "id": str(topic_tree.internal_energy.id),
        "module": "内能",
        "chapter": "第十三章 内能",
    }]


def test_validate_selected_ids_rejects_candidate_escape():
    with pytest.raises(ControlCatalogSelectionError):
        validate_selected_ids(["kp-1"], ["kp-2"])
```

- [ ] **Step 2: 验证红灯**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/knowledge/tests/test_controlled_catalog_service.py -q
```

Expected: FAIL because目录服务与 `ControlCatalogSelectionError` 不存在。

- [ ] **Step 3: 实现候选服务**

按 `subject`、`stage`、启用状态读取根主题；按 `parent_id` 读取子主题；只允许叶子主题读取 `KnowledgeTopicPoint` 并通过字符串 ID 查询现有 `KnowledgePoint`，返回 `id`、`module`、`chapter`、`full_label`。校验函数必须去重、保持模型返回顺序、要求数量 1 到 5，并在候选集外 ID、禁用节点、空 ID 时抛出 `ControlCatalogSelectionError`。

- [ ] **Step 4: 验证绿灯**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/knowledge/tests/test_controlled_catalog_service.py -q
```

Expected: PASS。

- [ ] **Step 5: 提交本任务**

```powershell
git add apps/knowledge/controlled_catalog.py apps/knowledge/tests/test_controlled_catalog_service.py
git commit -m "feat: add controlled taxonomy candidate service"
```

## Task 4: 三阶段 AI 响应契约、组件与提示词

**Files:**
- Modify: `apps/common/ai/schemas.py`
- Modify: `apps/common/ai/components/question_probe.py`
- Modify: `apps/common/ai/components/__init__.py`
- Modify: `apps/common/ai/config.py`
- Modify: `config/ai_config.cfg`
- Modify: `apps/common/ai/tests/test_question_components.py`
- Modify: `apps/common/ai/tests/test_config.py`

**Interfaces:**
- `TaxonomyScopeResponse(subject, stage, topic_id, question_type, difficulty_level, normalized_text, confidence)`。
- `TaxonomySubtopicResponse(subtopic_id | None, confidence)`。
- `TaxonomyKnowledgeResponse(knowledge_point_ids, difficulty_score, difficulty_reason, confidence)`。
- AI task keys `question_probe`、`knowledge_subtopic_select`、`knowledge_point_select`，都路由到 `qwen3.7-flash`。

- [ ] **Step 1: 写入失败组件契约测试**

```python
def test_knowledge_selection_rejects_score_outside_selected_level_range():
    component = KnowledgePointSelectComponent(RecordingAIClient({
        "knowledge_point_select": json.dumps({
            "knowledge_point_ids": ["kp-1"],
            "difficulty_score": 4.1,
            "difficulty_reason": "综合应用",
            "confidence": 0.9,
        }),
    }))
    with pytest.raises(AIResponseError, match="difficulty level"):
        component.run(QuestionInput(
            stem="题目", metadata={"difficulty_level": "L3", "candidates": [{"id": "kp-1"}]},
        ))
```

- [ ] **Step 2: 验证红灯**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/common/ai/tests/test_question_components.py -k "knowledge_selection_rejects_score" -q
```

Expected: FAIL because三阶段组件与分级难度校验不存在。

- [ ] **Step 3: 实现严格 Schema、组件与配置**

在 `schemas.py` 用 Pydantic 严格限定 subject、stage、difficulty_level、ID 列表、confidence 和一位小数分值。`KnowledgePointSelectComponent.validate_result()` 必须校验分值位于当前 `difficulty_level` 的区间；候选 ID 归属校验仍由目录服务在编排层执行。

在 `ai_config.cfg` 为三个阶段提供固定 JSON 输出提示词：第一次提供一级主题候选，第二次提供子主题候选，第三次提供标准知识点候选并明示“只能返回输入的 ID”。在 `config.py` 注册两个新 task key，禁止更改 provider/model。

- [ ] **Step 4: 验证绿灯与配置完整性**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/common/ai/tests/test_question_components.py -k "taxonomy or knowledge_selection" -q
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/common/ai/tests/test_config.py -q
```

Expected: PASS；默认配置中的三个任务均显示 `qwen/qwen3.7-flash/300.0`。

- [ ] **Step 5: 提交本任务**

```powershell
git add apps/common/ai/schemas.py apps/common/ai/components/question_probe.py apps/common/ai/components/__init__.py apps/common/ai/config.py config/ai_config.cfg apps/common/ai/tests/test_question_components.py apps/common/ai/tests/test_config.py
git commit -m "feat: add controlled taxonomy AI selection components"
```

## Task 5: 探查编排、逐步保存与最终字段回写

**Files:**
- Modify: `apps/common/ai_service.py`
- Modify: `apps/review/tasks.py`
- Modify: `apps/common/ai/tests/test_review_compatibility.py`
- Modify: `apps/review/test_course_ai_reconcile.py`

**Interfaces:**
- `AIReviewService.process_question_probe(question_id, model=None) -> dict` 返回 `scope`、可选 `subtopic`、`knowledge`、`errors`。
- `AIReviewService.save_results_to_question(question_id, results) -> None` 每阶段可独立调用。
- `is_ai_probe_complete(question) -> bool` 要求受控主题路径、标准知识点关联、difficulty_level 与 difficulty 均有效。

- [ ] **Step 1: 写入失败逐步保存测试**

```python
@pytest.mark.django_db
def test_probe_persists_scope_before_later_knowledge_selection_fails(question, topic_tree):
    service = AIReviewService(component_factory=failing_leaf_selection_factory(topic_tree))
    result = service.process_question_probe(str(question.id))
    question.refresh_from_db()
    assert question.subject == "physics"
    assert question.question_type == "single_choice"
    assert question.ai_probe_result["taxonomy"]["scope"]["topic_id"] == str(topic_tree.thermal.id)
    assert question.knowledge_points == []
    assert result["errors"]["knowledge"]


@pytest.mark.django_db
def test_probe_uses_last_selected_standard_point_for_taxonomy_and_score(question, topic_tree):
    result = completed_three_stage_result(topic_tree, ids=["kp-1", "kp-2"], level="L3", score=3.2)
    AIReviewService().save_results_to_question(str(question.id), result)
    question.refresh_from_db()
    assert question.difficulty_level == "L3"
    assert question.difficulty == Decimal("3.20")
    assert question.knowledge_points[-1]["id"] == "kp-2"
    assert question.ai_probe_result["derived_taxonomy"]["knowledge_point_id"] == "kp-2"
```

- [ ] **Step 2: 验证红灯**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/common/ai/tests/test_review_compatibility.py -k "scope_before_later or last_selected_standard" -q
```

Expected: FAIL because旧流程仍调用自由知识点分析，且未持久化 `difficulty_level`。

- [ ] **Step 3: 实现三阶段编排和缓存失效**

将旧自由文本 `analyze_knowledge_points()` 从新探查路径移除。第一阶段读取根主题候选；若该主题存在子主题，执行第二阶段；第三阶段读取叶子标准知识点候选并写回正式关联。

每一阶段完成后，调用 `save_results_to_question()` 写入 `ai_probe_result["taxonomy"]`。缓存键必须包含题目输入哈希、`catalog_version` 和路径；目录版本改变仅使依赖该路径的后续阶段失效。

第三阶段校验通过后，将 `difficulty_level` 和两位小数 `difficulty` 写入题目；按返回 ID 顺序保存 `knowledge_points`，最后一个 ID 的本地节点反推学科、学段、年级、学期、章节。任何失败不清除前序成功字段。

- [ ] **Step 4: 验证绿灯及旧兼容回归**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/common/ai/tests/test_review_compatibility.py apps/review/test_course_ai_reconcile.py -q
```

Expected: PASS；旧任务在新受控探查完成后不重复派发。

- [ ] **Step 5: 提交本任务**

```powershell
git add apps/common/ai_service.py apps/review/tasks.py apps/common/ai/tests/test_review_compatibility.py apps/review/test_course_ai_reconcile.py
git commit -m "feat: persist controlled three-stage AI probe results"
```

## Task 6: API 表达、历史补齐命令与可观测性

**Files:**
- Modify: `apps/study/serializers.py`
- Create: `apps/common/management/commands/reconcile_controlled_probe_taxonomy.py`
- Create: `apps/common/tests/test_reconcile_controlled_probe_taxonomy.py`
- Modify: `docs/ai_public_component_flow.md`

**Interfaces:**
- Question API 返回 `difficulty_level` 与数值 `difficulty`。
- 命令：`reconcile_controlled_probe_taxonomy --tag <tag> [--dry-run] [--limit N]`。
- 命令只创建探查补齐任务，绝不创建 A/B/C 答案任务。

- [ ] **Step 1: 写入失败历史补齐测试**

```python
@pytest.mark.django_db
def test_reconcile_command_queues_only_questions_missing_controlled_probe(tagged_questions, monkeypatch):
    enqueue = MagicMock()
    monkeypatch.setattr("apps.common.management.commands.reconcile_controlled_probe_taxonomy.enqueue_probe", enqueue)
    call_command("reconcile_controlled_probe_taxonomy", tag="9年级秋季班课件练习")
    assert enqueue.call_args_list == [call(str(tagged_questions.missing_probe.id))]
    assert tagged_questions.completed_probe.id not in [args[0][0] for args in enqueue.call_args_list]
```

- [ ] **Step 2: 验证红灯**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/common/tests/test_reconcile_controlled_probe_taxonomy.py -q
```

Expected: FAIL because历史补齐命令不存在。

- [ ] **Step 3: 实现 API、补齐命令和文档**

序列化器同时返回 `difficulty_level`、`difficulty` 与兼容的难度标签。命令按标签筛题、跳过已有完整受控探查的题、在 `--dry-run` 下只打印计划、在正常模式下通过既有 AI 队列提交探查任务；输出总数、跳过数、排队数和失败原因分类。

文档更新为三级受控候选选择，移除自由文本知识点输出描述，说明 `difficulty_level` 与 `difficulty` 的区别。

- [ ] **Step 4: 验证绿灯与全量相关回归**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/common/tests/test_reconcile_controlled_probe_taxonomy.py apps/common/ai/tests apps/review/test_course_ai_reconcile.py -q
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' manage.py check
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' manage.py migrate --plan
```

Expected: tests PASS；系统检查无问题；迁移计划仅包含受控目录与 `difficulty_level` 迁移。

- [ ] **Step 5: 提交本任务**

```powershell
git add apps/study/serializers.py apps/common/management/commands/reconcile_controlled_probe_taxonomy.py apps/common/tests/test_reconcile_controlled_probe_taxonomy.py docs/ai_public_component_flow.md
git commit -m "feat: expose and reconcile controlled AI probe taxonomy"
```

## Task 7: 本地迁移、抽样压测与生产发布前核验

**Files:**
- Modify: `docs/ai_public_component_flow.md`
- Test: `apps/common/ai/tests/test_review_compatibility.py`

**Interfaces:**
- Local command sequence applies migration, imports directory, dry-runs 277 题标签范围，再以少量题提交真实队列。
- Produces a release evidence record:目录覆盖率、三阶段成功率、正式知识点绑定率、阶段失败原因。

- [ ] **Step 1: 写入失败抽样验收测试**

```python
@pytest.mark.django_db
def test_controlled_probe_completed_question_is_visible_in_tree_filter(question, topic_tree):
    complete_controlled_probe(question, topic_tree, level="L3", score="3.20")
    response = teacher_client.get("/api/v1/questions/", {
        "knowledge_point_id": str(topic_tree.internal_energy.id),
    })
    assert str(question.id) in {item["id"] for item in response.data["data"]["items"]}
```

- [ ] **Step 2: 验证红灯**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/study/tests/test_question_scope.py -k "controlled_probe_completed" -q
```

Expected: FAIL before新正式关联写入与筛选链路全部就绪。

- [ ] **Step 3: 执行本地发布前流程**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' manage.py migrate
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' manage.py import_controlled_topic_catalog --path config/controlled_knowledge_topics.json
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' manage.py reconcile_controlled_probe_taxonomy --tag '9年级秋季班课件练习' --dry-run
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' manage.py reconcile_controlled_probe_taxonomy --tag '9年级秋季班课件练习' --limit 5
```

记录五题的每阶段结果；要求所有最终知识点均有标准 ID，题库知识树筛选可返回对应题目。

- [ ] **Step 4: 验证绿灯和工作树完整性**

Run:

```powershell
& 'C:\Users\johng\miniconda3\envs\ai-tools\python.exe' -m pytest apps/study/tests/test_question_scope.py -k "controlled_probe_completed" -q
git diff --check
git status --short
```

Expected: PASS；无 diff 空白错误；只包含本计划涉及的受跟踪文件。

- [ ] **Step 5: 提交本任务**

```powershell
git add apps/study/tests/test_question_scope.py docs/ai_public_component_flow.md
git commit -m "test: verify controlled probe tree visibility"
```
# 模块粒度修订（2026-08-29）

本计划中先前使用的 `KnowledgeTopicPoint` 与 `knowledge_point_ids` 均由 `KnowledgeTopicModule` 与 `knowledge_modules` 替代。第三阶段候选总量限定为本地 `knowledge_points.module` 的去重模块（当前约 470 个）；选定后，服务端按“科目 + 学段 + 叶子章节 + module”解析实际树节点 ID，保持题库筛选兼容。
