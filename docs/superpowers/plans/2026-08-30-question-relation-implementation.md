# 关联题 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在题库中提供可审计的人工关联题建立、查看与解除能力，候选题必须为同学科、难度差不超过 0.5 且共享至少一个标准知识点。

**Architecture:** 在 `apps.study` 维护一张规范化题对的独立关联表，并在 `apps.study.question_views` 增加关联题列表、候选题、批量创建和单条解除接口。前端沿用 `QuestionDetailCard` 的 `related` 事件，在 `question-bank.vue` 中替换旧“类似题”弹窗为带两个标签页的“关联题”弹窗；所有读写均通过 `questionApi`。

**Tech Stack:** Django 5.2、Django REST Framework、PostgreSQL、pytest、Vue 3、UniApp/Vite、TypeScript。

**Spec:** `docs/superpowers/specs/2026-08-30-question-relation-design.md`

## Global Constraints

- 仅修改 `front` 目录内文件。
- 使用独立 `QuestionRelation` 表；同一对题仅保存为按 UUID 字符串升序规范化的一行。
- 候选题必须同学科、难度在闭区间 `±0.5`、至少共享一个按 `id`、`module`、名称优先级规范化后的知识点。
- 解除关系只删除关联记录，不删除题目、答案、知识点或其他关联；重复解除返回成功且 `removed: false`。
- 沿用既有教师教学范围、题目可见性、认证和 `{'code', 'message', 'data', 'trace_id'}` 响应封装。
- 不删除旧 `/similar/` 接口，避免影响范围外调用；新前端只调用关联题接口。

---

### Task 1: 关联表与规范化服务

**Files:**
- Modify: `apps/study/models.py: QuestionTagRelation 之后`
- Create: `apps/study/migrations/0005_questionrelation.py`
- Create: `apps/study/question_relation_service.py`
- Test: `apps/study/tests/test_question_relations.py`

**Interfaces:**
- Consumes: `parser.ExamQuestion`、`accounts.UserAccount`、`ExamQuestion.subject`、`ExamQuestion.difficulty`、`ExamQuestion.knowledge_points`。
- Produces: `QuestionRelation` 模型；`canonical_question_pair(question_a, question_b) -> tuple[ExamQuestion, ExamQuestion]`；`knowledge_point_keys(raw_points) -> set[str]`；`find_relation_candidates(question, visible_questions) -> tuple[list[ExamQuestion], str | None]`。

- [ ] **Step 1: 写入失败的模型与服务单元测试**

```python
def test_canonical_pair_is_unique_and_readable_from_both_directions(teacher, questions):
    relation = QuestionRelation.create_for_questions(questions[1], questions[0], teacher)
    assert str(relation.question_left_id) < str(relation.question_right_id)
    assert QuestionRelation.for_question(questions[0]).get() == relation
    assert QuestionRelation.for_question(questions[1]).get() == relation

def test_candidate_service_accepts_shared_id_or_module_and_inclusive_half_point_boundary(questions):
    candidates, reason = find_relation_candidates(questions['origin'], ExamQuestion.objects.all())
    assert reason is None
    assert {item.id for item in candidates} == {questions['id_match'].id, questions['module_match'].id}

def test_relation_cannot_point_to_itself_or_duplicate_pair(teacher, questions):
    with pytest.raises(ValidationError):
        QuestionRelation.create_for_questions(questions['origin'], questions['origin'], teacher)
    QuestionRelation.create_for_questions(questions['origin'], questions['id_match'], teacher)
    with pytest.raises(IntegrityError):
        QuestionRelation.create_for_questions(questions['id_match'], questions['origin'], teacher)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest apps/study/tests/test_question_relations.py -q --reuse-db`

Expected: FAIL，因为 `QuestionRelation`、`canonical_question_pair`、`knowledge_point_keys` 与 `find_relation_candidates` 尚不存在。

- [ ] **Step 3: 实现最小模型、迁移和服务**

```python
class QuestionRelation(models.Model):
    question_left = models.ForeignKey('parser.ExamQuestion', on_delete=models.CASCADE, related_name='left_relations')
    question_right = models.ForeignKey('parser.ExamQuestion', on_delete=models.CASCADE, related_name='right_relations')
    created_by = models.ForeignKey(UserAccount, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['question_left', 'question_right'], name='uq_question_relation_pair'),
        ]

    @classmethod
    def create_for_questions(cls, question_a, question_b, created_by):
        left, right = canonical_question_pair(question_a, question_b)
        if left.pk == right.pk:
            raise ValidationError('题目不能关联自身')
        return cls.objects.create(question_left=left, question_right=right, created_by=created_by)
```

`question_relation_service.py` 先将 `raw_points` 中的字典或字符串统一为 `id:<value>`、`module:<value>`、`name:<value>` 键；候选数据库初筛为相同 `subject`、`difficulty__gte=origin-0.5`、`difficulty__lte=origin+0.5`、排除原题与已关联 ID，再由集合交集筛选。原题缺少学科、难度或知识点时返回空列表与固定原因字符串。

- [ ] **Step 4: 创建并检查迁移**

Run: `python manage.py makemigrations study --name questionrelation`

Expected: 仅生成 `apps/study/migrations/0005_questionrelation.py`，包含 UUID 主键、两个题目外键、创建人、时间和联合唯一约束。

Run: `python manage.py migrate study`

Expected: `study.0005_questionrelation... OK`。

- [ ] **Step 5: 运行 Task 1 测试确认通过**

Run: `python -m pytest apps/study/tests/test_question_relations.py -q --reuse-db`

Expected: PASS，涵盖顺序规范化、自关联拒绝、唯一约束、双向查询、ID/module/名称知识点匹配和 `±0.5` 边界。

- [ ] **Step 6: 提交 Task 1**

```bash
git add apps/study/models.py apps/study/migrations/0005_questionrelation.py apps/study/question_relation_service.py apps/study/tests/test_question_relations.py
git commit -m "feat: add question relation model and candidates"
```

### Task 2: 关联题 REST 接口与授权边界

**Files:**
- Modify: `apps/study/question_views.py: imports、similar_questions 附近`
- Modify: `apps/study/urls.py: question UUID 路由之前`
- Modify: `apps/study/tests/test_question_relations.py`

**Interfaces:**
- Consumes: Task 1 的 `QuestionRelation`、`canonical_question_pair`、`find_relation_candidates`；既有 `_teacher_question_scope_error(request, question)`；`QuestionListSerializer`。
- Produces:
  - `GET /api/v1/questions/{question_id}/relations/`
  - `GET /api/v1/questions/{question_id}/relation-candidates/`
  - `POST /api/v1/questions/{question_id}/relations/`
  - `DELETE /api/v1/questions/{question_id}/relations/{related_id}/`

- [ ] **Step 1: 写入失败的接口测试**

```python
def test_relation_candidates_enforce_scope_subject_difficulty_knowledge_and_pagination(teacher_client, relation_questions):
    response = teacher_client.get(f'/api/v1/questions/{relation_questions.origin.id}/relation-candidates/', {'page': 1, 'page_size': 50})
    assert response.status_code == 200
    assert response.data['data']['total'] == 2
    assert response.data['data']['items'][0]['common_knowledge_point_names']

def test_create_list_and_remove_relation_is_direction_independent_and_idempotent(teacher_client, relation_questions):
    created = teacher_client.post(f'/api/v1/questions/{relation_questions.origin.id}/relations/', {'question_ids': [str(relation_questions.match.id)]}, format='json')
    assert created.data['data']['created_count'] == 1
    listed = teacher_client.get(f'/api/v1/questions/{relation_questions.match.id}/relations/')
    assert [item['id'] for item in listed.data['data']['items']] == [str(relation_questions.origin.id)]
    removed = teacher_client.delete(f'/api/v1/questions/{relation_questions.origin.id}/relations/{relation_questions.match.id}/')
    repeated = teacher_client.delete(f'/api/v1/questions/{relation_questions.match.id}/relations/{relation_questions.origin.id}/')
    assert removed.data['data']['removed'] is True
    assert repeated.data['data']['removed'] is False
```

- [ ] **Step 2: 运行接口测试确认失败**

Run: `python -m pytest apps/study/tests/test_question_relations.py -q --reuse-db`

Expected: FAIL 或 404，因为四个新 URL 和视图尚未注册。

- [ ] **Step 3: 实现分页序列化和四个视图**

```python
def _relation_item(question, common_names=None):
    return {
        'id': str(question.id),
        'question_no': question.question_no,
        'stem_preview': preview_text(question.stem, question.subquestions, question.tables, limit=120),
        'difficulty': question.difficulty,
        'knowledge_points_display': QuestionListSerializer(question).get_knowledge_points_display(question),
        'common_knowledge_point_names': common_names or [],
    }

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def question_relation_detail(request, question_id, related_id):
    question, related = _get_visible_question_pair(request, question_id, related_id)
    left, right = canonical_question_pair(question, related)
    removed, _ = QuestionRelation.objects.filter(question_left=left, question_right=right).delete()
    return Response({'code': 0, 'message': 'success', 'data': {'removed': bool(removed)}, 'trace_id': ''})
```

实现 `_get_visible_question_pair`：分别加载两题并分别调用 `_teacher_question_scope_error`；POST/DELETE 仅允许题库管理角色，读取接口沿用既有题目读取范围。分页参数沿用题库列表限制 `1..100`；批量创建在 `transaction.atomic()` 内逐个规范化、跳过自关联/不可见/不存在 ID，并以 `get_or_create` 统计 `created_count`、`existing_count`、`invalid_question_ids`。

- [ ] **Step 4: 注册 URL，确保顺序正确**

```python
path('<uuid:question_id>/relations/', question_views.question_relations, name='question-relations'),
path('<uuid:question_id>/relations/<uuid:related_id>/', question_views.question_relation_detail, name='question-relation-detail'),
path('<uuid:question_id>/relation-candidates/', question_views.question_relation_candidates, name='question-relation-candidates'),
```

将以上三条置于 `path('<uuid:question_id>', ...)` 通用详情路由之前，避免被详情路由抢占。

- [ ] **Step 5: 运行接口和范围回归测试**

Run: `python -m pytest apps/study/tests/test_question_relations.py apps/study/tests/test_question_scope.py -q --reuse-db`

Expected: PASS；异学科、无共同知识点、超出难度范围、已关联题、不可见题均不会出现在候选中；解除后关系消失且题目仍存在。

- [ ] **Step 6: 提交 Task 2**

```bash
git add apps/study/question_views.py apps/study/urls.py apps/study/tests/test_question_relations.py
git commit -m "feat: expose question relation APIs"
```

### Task 3: 题库前端“关联题”双标签弹窗

**Files:**
- Modify: `uniapp/src/api/questions.ts: questionApi.similar 附近`
- Modify: `uniapp/src/components/QuestionDetailCard.vue: compact 与 footer 的 related 按钮`
- Modify: `uniapp/src/pages/teacher/question-bank.vue: related 弹窗、related 状态与 handleRelated`
- Test: `uniapp/src/pages/teacher/question-bank.vue` 的静态交互断言或项目既有 Vue 测试目录中新增 `question-bank.relations.spec.ts`

**Interfaces:**
- Consumes: Task 2 的四个 HTTP 路径。
- Produces: `questionApi.relations(id, params)`、`questionApi.relationCandidates(id, params)`、`questionApi.createRelations(id, questionIds)`、`questionApi.removeRelation(id, relatedId)`；前端“关联题”弹窗的查看、选择、建立与解除交互。

- [ ] **Step 1: 写入失败的前端交互测试或源码契约断言**

```ts
it('uses relation APIs and renders candidate and linked tabs', async () => {
  expect(questionApi.relationCandidates).toBeDefined()
  expect(questionApi.createRelations).toBeDefined()
  expect(questionApi.removeRelation).toBeDefined()
  expect(questionBankTemplate).toContain('可关联题')
  expect(questionBankTemplate).toContain('已关联题')
  expect(questionBankTemplate).toContain('解除关联')
})
```

- [ ] **Step 2: 运行前端测试确认失败**

Run: `npm run test -- --run question-bank.relations.spec.ts`

Expected: FAIL，因为新 API 方法、标签文案与解除按钮尚不存在。若仓库没有 `test` 脚本，改用已安装测试工具的等价单文件命令，并在提交说明中记录实际命令。

- [ ] **Step 3: 添加 API 客户端和严格数据类型**

```ts
export type QuestionRelationItem = {
  id: UUID
  question_no: string
  stem_preview: string
  difficulty: string | number | null
  knowledge_points_display: Array<{ id?: string; name: string }>
  common_knowledge_point_names?: string[]
}

relations: (id: UUID, params?: { page?: number; page_size?: number }) => get<any>(`/questions/${id}/relations/`, params),
relationCandidates: (id: UUID, params?: { page?: number; page_size?: number }) => get<any>(`/questions/${id}/relation-candidates/`, params),
createRelations: (id: UUID, questionIds: UUID[]) => post<any>(`/questions/${id}/relations/`, { question_ids: questionIds }),
removeRelation: (id: UUID, relatedId: UUID) => del<any>(`/questions/${id}/relations/${relatedId}/`),
```

- [ ] **Step 4: 替换按钮与弹窗状态机**

在 `QuestionDetailCard.vue` 保持事件名 `related` 不变，仅将紧凑和标准视图按钮文案改为“关联题”。在 `question-bank.vue` 新增以下状态：

```ts
const relationVisible = ref(false)
const relationQuestionId = ref<UUID | null>(null)
const relationTab = ref<'candidates' | 'linked'>('candidates')
const relationCandidates = ref<QuestionRelationItem[]>([])
const linkedQuestions = ref<QuestionRelationItem[]>([])
const selectedRelationIds = ref<UUID[]>([])
const relationLoading = ref(false)
const relationReason = ref('')
```

`openRelations(id)` 初始化为候选标签、清空跨题残留的选择并加载候选；`loadRelationCandidates()` 与 `loadLinkedQuestions()` 从 `res.data.items`、`res.data.total` 读取分页结果；“关联”调用 `createRelations` 后清空选择，重新加载两页并切换到 `linked`；“解除关联”使用 `uni.showModal` 确认，确认后调用 `removeRelation`，成功时重新加载两个列表，失败时不改动本地列表并显示接口消息。弹窗头部使用显式右上角关闭按钮，遮罩点击也关闭。

- [ ] **Step 5: 运行前端测试与 H5 构建**

Run: `npm run test -- --run question-bank.relations.spec.ts`

Expected: PASS。

Run: `node node_modules/@dcloudio/vite-plugin-uni/bin/uni.js build`

Expected: 退出码 0；没有模板标签、TypeScript 或 API 调用错误。

- [ ] **Step 6: 提交 Task 3**

```bash
git add uniapp/src/api/questions.ts uniapp/src/components/QuestionDetailCard.vue uniapp/src/pages/teacher/question-bank.vue uniapp/src/pages/teacher/question-bank.relations.spec.ts
git commit -m "feat: manage question relations from question bank"
```

### Task 4: 全量验证、迁移检查与交付说明

**Files:**
- Modify: `docs/superpowers/specs/2026-08-30-question-relation-design.md`（仅在实现发现与已确认规格不一致时，先获得用户确认后再更新）
- Modify: `docs/superpowers/plans/2026-08-30-question-relation-implementation.md`（勾选已完成步骤）

**Interfaces:**
- Consumes: Tasks 1–3 的模型、API 和前端页面。
- Produces: 已应用迁移、可重复运行的测试证据和面向用户的完成说明。

- [ ] **Step 1: 检查迁移没有遗漏**

Run: `python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`。

Run: `python manage.py migrate --plan`

Expected: 本地数据库仅显示尚未执行的既有迁移；若 `study.0005_questionrelation` 未应用，先执行 `python manage.py migrate study` 后重新检查。

- [ ] **Step 2: 运行后端回归测试**

Run: `python -m pytest apps/study/tests/test_question_relations.py apps/study/tests/test_question_scope.py -q --reuse-db`

Expected: PASS。

Run: `python manage.py check`

Expected: `System check identified no issues`。

- [ ] **Step 3: 执行本地人工验收**

启动后端与 H5 后，以具备教师题库权限的账号验证：

1. 点击题目的“关联题”打开弹窗，默认“可关联题”。
2. 候选只包含同学科、难度差不超过 0.5、共享知识点且未关联的题。
3. 多选建立关联后，题目出现在“已关联题”。
4. 点击“解除关联”并确认后，题目从“已关联题”消失、重新出现在“可关联题”；原题和被关联题仍可打开，答案和知识点不变。
5. 重复解除同一题不产生前端错误。

- [ ] **Step 4: 提交验收文档与计划状态**

```bash
git add docs/superpowers/specs/2026-08-30-question-relation-design.md docs/superpowers/plans/2026-08-30-question-relation-implementation.md
git commit -m "docs: record question relation verification"
```

