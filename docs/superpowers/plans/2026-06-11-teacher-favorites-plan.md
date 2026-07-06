# 教师端题库管理与我的精选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 uni-app 教师端新增题库管理（知识点树+题目列表）和我的精选功能，后端 tiku Django 提供精选 API 和知识点树 API。

**Architecture:** 后端 tiku 新增 TeacherFavorite 模型和 REST API 端点；前端 uni-app 新增 bank.vue 和 favorites.vue 页面，通过 API 调用实现精选操作和知识点树展示。

**Tech Stack:** Django 5 + DRF (后端), uni-app + Vue 3 + TypeScript + Pinia (前端)

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `tiku/apps/review/models.py` | **修改** | 新增 TeacherFavorite 模型 |
| `tiku/apps/review/views.py` | **修改** | 新增精选 CRUD API + 知识点树 API |
| `tiku/apps/review/urls.py` | **修改** | 注册新 API 路由 |
| `tiku/apps/review/serializers.py` | **修改** | 新增 FavoriteSerializer |
| `tiku/apps/knowledge/htmx_urls.py` 或 `views.py` | **修改** | 知识点树查询逻辑（或用 review app） |
| `front/uniapp/src/api/favorites.ts` | **新建** | 精选 API 封装 |
| `front/uniapp/src/api/knowledge.ts` | **新建** | 知识点树 API 封装 |
| `front/uniapp/src/pages/teacher/bank.vue` | **新建** | 题库列表页（知识点树+题目列表） |
| `front/uniapp/src/pages/teacher/favorites.vue` | **新建** | 我的精选页 |
| `front/uniapp/src/pages.json` | **修改** | 新增页面路由 |
| `front/uniapp/src/pages/teacher/*.vue` (所有) | **修改** | sidebar 菜单更新 |

---

### Task 1: 后端 — TeacherFavorite 模型 + 精选 API

**Files:**
- Modify: `tiku/apps/review/models.py`
- Modify: `tiku/apps/review/serializers.py`
- Modify: `tiku/apps/review/views.py`
- Modify: `tiku/apps/review/urls.py`

- [ ] **Step 1: 新增 TeacherFavorite 模型**

在 `tiku/apps/review/models.py` 末尾添加：

```python
class TeacherFavorite(models.Model):
    """Teacher's favorite questions."""
    user = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE,
        related_name='favorites', db_column='user_id'
    )
    question = models.ForeignKey(
        'parser.ExamQuestion', on_delete=models.CASCADE,
        related_name='favorited_by', db_column='question_id'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tiku_teacher_favorite'
        unique_together = [['user', 'question']]
        ordering = ['-created_at']
        verbose_name = '教师精选'
        verbose_name_plural = '教师精选'

    def __str__(self):
        return f'Favorite: User {self.user_id} -> Question {self.question_id}'
```

- [ ] **Step 2: 新增序列化器**

在 `tiku/apps/review/serializers.py` 中添加：

```python
class FavoriteSerializer(serializers.ModelSerializer):
    question_no = serializers.CharField(source='question.question_no', read_only=True)
    paper_title = serializers.CharField(source='question.paper.title', read_only=True)
    difficulty = serializers.DecimalField(source='question.difficulty', max_digits=4, decimal_places=2, read_only=True)
    knowledge_points_count = serializers.SerializerMethodField()

    class Meta:
        model = TeacherFavorite
        fields = ['id', 'question_id', 'question_no', 'paper_title', 'difficulty', 'knowledge_points_count', 'created_at']

    def get_knowledge_points_count(self, obj):
        kp = obj.question.knowledge_points
        if isinstance(kp, list):
            return len(kp)
        return 0
```

在 `tiku/apps/review/serializers.py` 文件顶部确保有：
```python
from apps.parser.models import ExamQuestion
```

- [ ] **Step 3: 新增精选 API 视图**

在 `tiku/apps/review/views.py` 中添加：

```python
from .models import TeacherFavorite
from .serializers import FavoriteSerializer

@api_view(['GET'])
def teacher_favorites(request):
    """Get current teacher's favorite questions."""
    user = request.user
    favorites = TeacherFavorite.objects.filter(user=user).select_related('question', 'question__paper')
    serializer = FavoriteSerializer(favorites, many=True)
    return Response({'success': True, 'data': serializer.data})

@api_view(['POST'])
def add_favorite(request):
    """Add a question to favorites."""
    user = request.user
    question_id = request.data.get('question_id')
    if not question_id:
        return Response({'success': False, 'error': 'question_id required'}, status=400)
    
    try:
        question = ExamQuestion.objects.get(id=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'success': False, 'error': 'Question not found'}, status=404)
    
    fav, created = TeacherFavorite.objects.get_or_create(user=user, question=question)
    if not created:
        return Response({'success': False, 'error': 'Already favorited'}, status=409)
    
    return Response({'success': True, 'data': {'id': fav.id}})

@api_view(['DELETE'])
def remove_favorite(request, favorite_id):
    """Remove a favorite question."""
    user = request.user
    try:
        fav = TeacherFavorite.objects.get(id=favorite_id, user=user)
        fav.delete()
        return Response({'success': True})
    except TeacherFavorite.DoesNotExist:
        return Response({'success': False, 'error': 'Favorite not found'}, status=404)
```

在 `tiku/apps/review/views.py` 文件顶部确保有：
```python
from apps.parser.models import ExamQuestion
```

- [ ] **Step 4: 注册 API 路由**

在 `tiku/apps/review/urls.py` 中添加路由。找到现有的 `urlpatterns`，添加：

```python
path('api/v1/teacher/favorites/', views.teacher_favorites, name='teacher-favorites'),
path('api/v1/teacher/favorites/add/', views.add_favorite, name='add-favorite'),
path('api/v1/teacher/favorites/<int:favorite_id>/', views.remove_favorite, name='remove-favorite'),
```

- [ ] **Step 5: 创建数据库迁移**

```bash
cd tiku
python manage.py makemigrations review -n add_teacher_favorite
```

Expected output: `Migrations for 'review': apps/review/migrations/0XXX_add_teacher_favorite.py`

- [ ] **Step 6: Commit**

```bash
cd D:\workspace\code\qidi
git add tiku/apps/review/models.py tiku/apps/review/serializers.py tiku/apps/review/views.py tiku/apps/review/urls.py tiku/apps/review/migrations/
git commit -m "feat: add TeacherFavorite model and favorites API

- TeacherFavorite model with unique_together(user, question)
- GET /api/v1/teacher/favorites - list favorites
- POST /api/v1/teacher/favorites/add - add favorite (409 if duplicate)
- DELETE /api/v1/teacher/favorites/<id> - remove favorite
- FavoriteSerializer with question details

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 后端 — 知识点树 API

**Files:**
- Modify: `tiku/apps/review/views.py`
- Modify: `tiku/apps/review/urls.py`
- Or modify: `tiku/apps/knowledge/views.py` if knowledge app exists

- [ ] **Step 1: 新增知识点树 API 视图**

在 `tiku/apps/review/views.py` 中添加：

```python
@api_view(['GET'])
def knowledge_tree(request):
    """Get knowledge point tree filtered by teacher's subject and stage."""
    user = request.user
    # Get teacher's subject and stage from user profile
    subject = getattr(user, 'subject', None) or request.query_params.get('subject')
    stage = getattr(user, 'stage', None) or request.query_params.get('stage')
    
    # Query knowledge points - adjust based on actual KnowledgePoint model
    from apps.knowledge.models import KnowledgePoint
    qs = KnowledgePoint.objects.all()
    if subject:
        qs = qs.filter(subject=subject)
    if stage:
        qs = qs.filter(stage=stage)
    
    # Build tree structure: grade -> semester -> knowledge_points
    tree = {}
    for kp in qs.order_by('grade', 'semester', 'name'):
        grade = kp.grade or '未分类'
        semester = kp.semester or '未分类'
        if grade not in tree:
            tree[grade] = {}
        if semester not in tree[grade]:
            tree[grade][semester] = []
        
        # Count questions for this knowledge point
        question_count = ExamQuestion.objects.filter(
            knowledge_points__contains=[{'id': kp.id}]
        ).count() if hasattr(kp, 'id') else 0
        
        tree[grade][semester].append({
            'id': kp.id,
            'name': kp.name,
            'question_count': question_count,
        })
    
    # Convert to list format
    result = []
    for grade_name, semesters in tree.items():
        grade_obj = {'name': grade_name, 'semesters': []}
        for sem_name, kps in semesters.items():
            grade_obj['semesters'].append({'name': sem_name, 'knowledge_points': kps})
        result.append(grade_obj)
    
    return Response({'success': True, 'data': {'grades': result}})
```

**注意**：上面的代码假设 `KnowledgePoint` 模型有 `grade`、`semester`、`subject`、`stage` 字段。如果实际模型字段不同，需要调整。请先读取 `tiku/apps/knowledge/models.py` 确认实际字段。

如果 `KnowledgePoint` 模型不存在或结构不同，使用简化版本：

```python
@api_view(['GET'])
def knowledge_tree(request):
    """Get knowledge point tree - simplified version using question data."""
    subject = request.query_params.get('subject', '')
    stage = request.query_params.get('stage', '')
    
    # Get distinct knowledge_points from questions
    questions = ExamQuestion.objects.all()
    if subject:
        questions = questions.filter(subject=subject)
    
    # Extract unique knowledge points
    kp_set = {}
    for q in questions:
        if q.knowledge_points and isinstance(q.knowledge_points, list):
            for kp in q.knowledge_points:
                kp_id = kp.get('id')
                if kp_id and kp_id not in kp_set:
                    kp_set[kp_id] = {'id': kp_id, 'name': kp.get('name', ''), 'question_count': 0}
                if kp_id:
                    kp_set[kp_id]['question_count'] += 1
    
    # Group by grade/semester if available
    result = [{'name': '全部', 'semesters': [{'name': '全部', 'knowledge_points': list(kp_set.values())}]}]
    
    return Response({'success': True, 'data': {'grades': result}})
```

- [ ] **Step 2: 注册 API 路由**

在 `tiku/apps/review/urls.py` 的 `urlpatterns` 中添加：

```python
path('api/v1/teacher/knowledge-tree/', views.knowledge_tree, name='knowledge-tree'),
```

- [ ] **Step 3: Commit**

```bash
cd D:\workspace\code\qidi
git add tiku/apps/review/views.py tiku/apps/review/urls.py
git commit -m "feat: add knowledge tree API endpoint

- GET /api/v1/teacher/knowledge-tree - returns grade/semester/knowledge_point tree
- Filters by teacher subject and stage
- Includes question_count per knowledge point

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 前端 — API 封装

**Files:**
- Create: `front/uniapp/src/api/favorites.ts`
- Create: `front/uniapp/src/api/knowledge.ts`

- [ ] **Step 1: 创建 favorites.ts**

```typescript
import { post, get, del } from '../utils/request'

export interface Favorite {
  id: number
  question_id: number
  question_no: string
  paper_title: string
  difficulty: number | null
  knowledge_points_count: number
  created_at: string
}

export const favoriteApi = {
  // GET /api/v1/teacher/favorites
  list: () => get<Favorite[]>('/teacher/favorites'),

  // POST /api/v1/teacher/favorites/add
  add: (question_id: number) => post<{ id: number }>('/teacher/favorites/add', { question_id }),

  // DELETE /api/v1/teacher/favorites/{id}
  remove: (id: number) => del(`/teacher/favorites/${id}`),
}
```

- [ ] **Step 2: 创建 knowledge.ts**

```typescript
import { get } from '../utils/request'

export interface KnowledgePoint {
  id: number
  name: string
  question_count: number
}

export interface Semester {
  name: string
  knowledge_points: KnowledgePoint[]
}

export interface Grade {
  name: string
  semesters: Semester[]
}

export interface KnowledgeTree {
  grades: Grade[]
}

export const knowledgeApi = {
  // GET /api/v1/teacher/knowledge-tree
  getTree: (params?: { subject?: string; stage?: string }) =>
    get<KnowledgeTree>('/teacher/knowledge-tree', params),
}
```

- [ ] **Step 3: Commit**

```bash
cd D:\workspace\code\qidi
git add front/uniapp/src/api/favorites.ts front/uniapp/src/api/knowledge.ts
git commit -m "feat: add favorites and knowledge API wrappers for uni-app

- favoriteApi: list, add, remove
- knowledgeApi: getTree with Grade/Semester/KnowledgePoint types

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 前端 — 题库列表页（bank.vue）

**Files:**
- Create: `front/uniapp/src/pages/teacher/bank.vue`
- Modify: `front/uniapp/src/pages.json`

- [ ] **Step 1: 注册页面路由**

在 `front/uniapp/src/pages.json` 的 `pages` 数组中，在 `pages/teacher/import` 之后添加：

```json
{ "path": "pages/teacher/bank", "style": { "navigationBarTitleText": "题库管理" } },
{ "path": "pages/teacher/favorites", "style": { "navigationBarTitleText": "我的精选" } },
```

- [ ] **Step 2: 创建 bank.vue**

```vue
<template>
  <view class="bank">
    <!-- Left sidebar -->
    <view class="sidebar">
      <view class="sidebar-logo">A自习室</view>
      <view class="sidebar-user">
        <text class="user-name">{{ userInfo.display_name }}</text>
        <text class="user-role">教师</text>
      </view>
      <view class="nav-items">
        <view class="nav-item" @click="goWorkbench">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">工作台</text>
        </view>
        <view class="nav-group">
          <view class="nav-group-title">题库管理</view>
          <view class="nav-item active">
            <text class="nav-icon">&#128218;</text>
            <text class="nav-text">题库列表</text>
          </view>
          <view class="nav-item" @click="goFavorites">
            <text class="nav-icon">&#11088;</text>
            <text class="nav-text">我的精选</text>
          </view>
        </view>
        <view class="nav-item" @click="goAudit">
          <text class="nav-icon">&#128269;</text>
          <text class="nav-text">OCR审核</text>
        </view>
        <view class="nav-item" @click="goCreateMission">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">创建任务</text>
        </view>
        <view class="nav-item" @click="goClasses">
          <text class="nav-icon">&#127963;</text>
          <text class="nav-text">班级管理</text>
        </view>
        <view class="nav-item nav-logout" @click="handleLogout">
          <text class="nav-icon">&#128682;</text>
          <text class="nav-text">退出登录</text>
        </view>
      </view>
    </view>

    <!-- Main content -->
    <view class="main">
      <!-- Left panel: Knowledge tree -->
      <view class="left-panel">
        <view class="panel-title">知识点</view>
        <view v-if="loadingTree" class="loading">加载中...</view>
        <view v-else class="tree">
          <view v-for="grade in tree" :key="grade.name" class="tree-grade">
            <view class="tree-node" @click="toggleGrade(grade)">
              <text class="tree-arrow">{{ grade.expanded ? '▼' : '▶' }}</text>
              <text class="tree-label">{{ grade.name }}</text>
            </view>
            <view v-if="grade.expanded" class="tree-children">
              <view v-for="sem in grade.semesters" :key="sem.name" class="tree-semester">
                <view class="tree-node" @click="toggleSemester(sem)">
                  <text class="tree-arrow">{{ sem.expanded ? '▼' : '▶' }}</text>
                  <text class="tree-label">{{ sem.name }}</text>
                </view>
                <view v-if="sem.expanded" class="tree-children">
                  <view v-for="kp in sem.knowledge_points" :key="kp.id"
                        class="tree-kp"
                        :class="{ selected: selectedKpId === kp.id }"
                        @click="selectKp(kp)">
                    <text class="kp-name">{{ kp.name }}</text>
                    <text class="kp-count">({{ kp.question_count }})</text>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>

      <!-- Right panel: Question list -->
      <view class="right-panel">
        <view class="panel-title">题目列表</view>
        <view v-if="!selectedKpId" class="empty">
          <text>请从左侧选择一个知识点</text>
        </view>
        <view v-else-if="loadingQuestions" class="loading">加载中...</view>
        <view v-else-if="questions.length === 0" class="empty">
          <text>该知识点下暂无题目</text>
        </view>
        <view v-else class="question-table">
          <view class="table-header">
            <text class="col col-no">编号</text>
            <text class="col col-source">来源</text>
            <text class="col col-diff">难度</text>
            <text class="col col-kp">知识点</text>
            <text class="col col-practice">练习</text>
            <text class="col col-error">出错</text>
            <text class="col col-action">操作</text>
          </view>
          <view v-for="q in questions" :key="q.id" class="table-row">
            <text class="col col-no">{{ q.question_no || q.id }}</text>
            <text class="col col-source">{{ q.paper_title || '-' }}</text>
            <text class="col col-diff">{{ difficultyText(q.difficulty) }}</text>
            <text class="col col-kp">{{ q.knowledge_points_count || 0 }}</text>
            <text class="col col-practice">{{ q.practice_count || 0 }}</text>
            <text class="col col-error">{{ q.error_count || 0 }}</text>
            <view class="col col-action">
              <view v-if="q.is_favorited" class="btn-favorited">已精选</view>
              <view v-else class="btn-favorite" @click="addFavorite(q)">加入精选</view>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { knowledgeApi, type Grade as ApiGrade, type KnowledgePoint } from '../../api/knowledge'
import { questionApi } from '../../api/questions'
import { favoriteApi } from '../../api/favorites'
import { authApi } from '../../api'
import { useUserStore } from '../../store'

interface Grade extends ApiGrade { expanded: boolean }
interface Semester { name: string; knowledge_points: KnowledgePoint[]; expanded: boolean }

const userInfo = ref({ display_name: '老师' })
const tree = ref<Grade[]>([])
const questions = ref<any[]>([])
const selectedKpId = ref<number | null>(null)
const loadingTree = ref(false)
const loadingQuestions = ref(false)
const userStore = useUserStore()

onMounted(async () => {
  try {
    const profile = await authApi.getProfile()
    if (profile.data) userInfo.value = profile.data
  } catch {}

  await loadTree()
})

async function loadTree() {
  loadingTree.value = true
  try {
    const subject = userStore.userInfo?.subject || ''
    const stage = userStore.userInfo?.stage || ''
    const res = await knowledgeApi.getTree({ subject, stage })
    tree.value = (res.data?.grades || []).map((g: Grade) => ({
      ...g,
      expanded: false,
      semesters: g.semesters.map((s: Semester) => ({ ...s, expanded: false })),
    }))
  } catch (e) {
    console.error('Failed to load knowledge tree:', e)
  } finally {
    loadingTree.value = false
  }
}

function toggleGrade(grade: Grade) { grade.expanded = !grade.expanded }
function toggleSemester(sem: Semester) { sem.expanded = !sem.expanded }

async function selectKp(kp: KnowledgePoint) {
  selectedKpId.value = kp.id
  loadingQuestions.value = true
  try {
    const res = await questionApi.list({ page: 1, page_size: 100 })
    questions.value = res.data || []
    // Mark favorited questions
    const favs = await favoriteApi.list()
    const favIds = new Set((favs.data || []).map((f: any) => f.question_id))
    questions.value.forEach((q: any) => { q.is_favorited = favIds.has(q.id) })
  } catch (e) {
    console.error('Failed to load questions:', e)
  } finally {
    loadingQuestions.value = false
  }
}

async function addFavorite(q: any) {
  try {
    await favoriteApi.add(q.id)
    q.is_favorited = true
  } catch (e: any) {
    if (e?.statusCode === 409) {
      q.is_favorited = true
    } else {
      uni.showToast({ title: '加入失败', icon: 'none' })
    }
  }
}

function difficultyText(d: number | null): string {
  if (!d) return '-'
  const n = Math.round(Number(d))
  const map: Record<number, string> = { 1: 'L1', 2: 'L2', 3: 'L3', 4: 'L4', 5: 'L5' }
  return map[n] || String(d)
}

function goWorkbench() { uni.navigateTo({ url: '/pages/teacher/workbench' }) }
function goFavorites() { uni.navigateTo({ url: '/pages/teacher/favorites' }) }
function goAudit() { uni.navigateTo({ url: '/pages/teacher/audit' }) }
function goCreateMission() { uni.navigateTo({ url: '/pages/teacher/mission-create' }) }
function goClasses() { uni.navigateTo({ url: '/pages/teacher/my-classes' }) }

async function handleLogout() {
  uni.showModal({
    title: '确认退出', content: '确定要退出登录吗？',
    success: async (res) => {
      if (res.confirm) {
        try { await authApi.logout() } catch {}
        userStore.logout()
        uni.reLaunch({ url: '/pages/login/index' })
      }
    }
  })
}
</script>

<style scoped>
.bank { display: flex; min-height: 100vh; background: #f0f2f5; }
.sidebar { width: 240px; background: #fff; box-shadow: 2px 0 8px rgba(0,0,0,0.06); display: flex; flex-direction: column; position: fixed; left: 0; top: 0; bottom: 0; z-index: 10; }
.sidebar-logo { padding: 30rpx 24rpx; font-size: 32rpx; font-weight: bold; color: #409eff; border-bottom: 1rpx solid #f0f0f0; }
.sidebar-user { padding: 24rpx; border-bottom: 1rpx solid #f0f0f0; }
.user-name { font-size: 26rpx; font-weight: bold; color: #333; display: block; }
.user-role { font-size: 22rpx; color: #999; margin-top: 4rpx; display: block; }
.nav-items { padding: 16rpx 0; flex: 1; }
.nav-item { display: flex; align-items: center; padding: 16rpx 24rpx; cursor: pointer; transition: background 0.2s; }
.nav-item:hover { background: #f5f5f5; }
.nav-item.active { background: #ecf5ff; color: #409eff; }
.nav-icon { font-size: 32rpx; margin-right: 12rpx; }
.nav-text { font-size: 26rpx; color: #333; }
.nav-logout:hover { background: #fff0f0; }
.nav-logout .nav-icon { opacity: 0.7; }
.nav-logout .nav-text { color: #e74c3c; }
.nav-group-title { padding: 8rpx 24rpx; font-size: 20rpx; color: #999; font-weight: bold; }

.main { margin-left: 240px; flex: 1; display: flex; padding: 30rpx 40rpx; gap: 20rpx; }
.left-panel { width: 300px; background: #fff; border-radius: 12rpx; padding: 20rpx; overflow-y: auto; max-height: 80vh; }
.right-panel { flex: 1; background: #fff; border-radius: 12rpx; padding: 20rpx; overflow-y: auto; max-height: 80vh; }
.panel-title { font-size: 28rpx; font-weight: bold; color: #333; padding: 10rpx 0 20rpx; border-bottom: 1rpx solid #f0f0f0; margin-bottom: 16rpx; }

.tree { }
.tree-grade { margin-bottom: 8rpx; }
.tree-node { display: flex; align-items: center; padding: 8rpx 12rpx; cursor: pointer; border-radius: 8rpx; }
.tree-node:hover { background: #f5f5f5; }
.tree-arrow { font-size: 20rpx; margin-right: 8rpx; width: 20rpx; text-align: center; }
.tree-label { font-size: 24rpx; color: #333; }
.tree-children { padding-left: 24rpx; }
.tree-semester { margin-bottom: 4rpx; }
.tree-kp { display: flex; justify-content: space-between; padding: 8rpx 12rpx 8rpx 28rpx; cursor: pointer; border-radius: 8rpx; }
.tree-kp:hover { background: #ecf5ff; }
.tree-kp.selected { background: #ecf5ff; }
.kp-name { font-size: 22rpx; color: #333; }
.kp-count { font-size: 20rpx; color: #999; }

.empty { text-align: center; padding: 80rpx; color: #999; font-size: 26rpx; }
.loading { text-align: center; padding: 40rpx; color: #409eff; font-size: 24rpx; }

.question-table { }
.table-header { display: flex; padding: 16rpx 8rpx; background: #f5f5f5; border-radius: 8rpx; font-size: 22rpx; font-weight: bold; color: #666; }
.table-row { display: flex; padding: 16rpx 8rpx; border-bottom: 1rpx solid #f0f0f0; font-size: 22rpx; align-items: center; }
.table-row:hover { background: #fafafa; }
.col { flex: 1; text-align: center; }
.col-no { flex: 0.8; }
.col-source { flex: 1.5; }
.col-diff { flex: 0.8; }
.col-kp { flex: 0.6; }
.col-practice { flex: 0.6; }
.col-error { flex: 0.6; }
.col-action { flex: 1; }

.btn-favorite { display: inline-block; padding: 8rpx 16rpx; background: #409eff; color: #fff; border-radius: 8rpx; font-size: 20rpx; cursor: pointer; }
.btn-favorite:hover { background: #337ecc; }
.btn-favorited { display: inline-block; padding: 8rpx 16rpx; background: #e8e8e8; color: #999; border-radius: 8rpx; font-size: 20rpx; }

@media (max-width: 768px) {
  .sidebar { width: 60px; }
  .sidebar-user, .nav-text, .nav-group-title { display: none; }
  .nav-item { justify-content: center; padding: 16rpx 0; }
  .nav-icon { margin-right: 0; }
  .main { margin-left: 60px; flex-direction: column; }
  .left-panel { width: auto; max-height: 30vh; }
  .right-panel { max-height: 60vh; }
}
</style>
```

- [ ] **Step 3: Commit**

```bash
cd D:\workspace\code\qidi
git add front/uniapp/src/pages.json front/uniapp/src/pages/teacher/bank.vue
git commit -m "feat: add bank.vue question bank list page

- Left panel: knowledge tree with grade/semester/knowledge_point hierarchy
- Right panel: question list table with favorite button
- Sidebar navigation with 题库管理 group
- Click knowledge point to load questions
- Click 加入精选 to add to favorites

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 前端 — 我的精选页（favorites.vue）

**Files:**
- Create: `front/uniapp/src/pages/teacher/favorites.vue`

- [ ] **Step 1: 创建 favorites.vue**

```vue
<template>
  <view class="favorites">
    <!-- Left sidebar -->
    <view class="sidebar">
      <view class="sidebar-logo">A自习室</view>
      <view class="sidebar-user">
        <text class="user-name">{{ userInfo.display_name }}</text>
        <text class="user-role">教师</text>
      </view>
      <view class="nav-items">
        <view class="nav-item" @click="goWorkbench">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">工作台</text>
        </view>
        <view class="nav-group">
          <view class="nav-group-title">题库管理</view>
          <view class="nav-item" @click="goBank">
            <text class="nav-icon">&#128218;</text>
            <text class="nav-text">题库列表</text>
          </view>
          <view class="nav-item active">
            <text class="nav-icon">&#11088;</text>
            <text class="nav-text">我的精选</text>
          </view>
        </view>
        <view class="nav-item" @click="goAudit">
          <text class="nav-icon">&#128269;</text>
          <text class="nav-text">OCR审核</text>
        </view>
        <view class="nav-item" @click="goCreateMission">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">创建任务</text>
        </view>
        <view class="nav-item" @click="goClasses">
          <text class="nav-icon">&#127963;</text>
          <text class="nav-text">班级管理</text>
        </view>
        <view class="nav-item nav-logout" @click="handleLogout">
          <text class="nav-icon">&#128682;</text>
          <text class="nav-text">退出登录</text>
        </view>
      </view>
    </view>

    <!-- Main content -->
    <view class="main">
      <view class="panel">
        <view class="panel-title">我的精选</view>
        <view v-if="loading" class="loading">加载中...</view>
        <view v-else-if="favorites.length === 0" class="empty">
          <text>还没有精选试题，去题库列表添加吧</text>
        </view>
        <view v-else class="question-table">
          <view class="table-header">
            <text class="col col-no">编号</text>
            <text class="col col-source">来源</text>
            <text class="col col-diff">难度</text>
            <text class="col col-kp">知识点</text>
            <text class="col col-action">操作</text>
          </view>
          <view v-for="f in favorites" :key="f.id" class="table-row">
            <text class="col col-no">{{ f.question_no }}</text>
            <text class="col col-source">{{ f.paper_title || '-' }}</text>
            <text class="col col-diff">{{ difficultyText(f.difficulty) }}</text>
            <text class="col col-kp">{{ f.knowledge_points_count }}</text>
            <view class="col col-action">
              <view class="btn-remove" @click="removeFavorite(f)">取消精选</view>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { favoriteApi, type Favorite } from '../../api/favorites'
import { authApi } from '../../api'
import { useUserStore } from '../../store'

const userInfo = ref({ display_name: '老师' })
const favorites = ref<Favorite[]>([])
const loading = ref(false)
const userStore = useUserStore()

onMounted(async () => {
  try {
    const profile = await authApi.getProfile()
    if (profile.data) userInfo.value = profile.data
  } catch {}

  await loadFavorites()
})

async function loadFavorites() {
  loading.value = true
  try {
    const res = await favoriteApi.list()
    favorites.value = res.data || []
  } catch (e) {
    console.error('Failed to load favorites:', e)
  } finally {
    loading.value = false
  }
}

async function removeFavorite(f: Favorite) {
  uni.showModal({
    title: '确认取消', content: `确定要取消精选题目 ${f.question_no} 吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await favoriteApi.remove(f.id)
          favorites.value = favorites.value.filter((item) => item.id !== f.id)
          uni.showToast({ title: '已取消', icon: 'success' })
        } catch (e) {
          uni.showToast({ title: '取消失败', icon: 'none' })
        }
      }
    }
  })
}

function difficultyText(d: number | null): string {
  if (!d) return '-'
  const n = Math.round(Number(d))
  const map: Record<number, string> = { 1: 'L1', 2: 'L2', 3: 'L3', 4: 'L4', 5: 'L5' }
  return map[n] || String(d)
}

function goWorkbench() { uni.navigateTo({ url: '/pages/teacher/workbench' }) }
function goBank() { uni.navigateTo({ url: '/pages/teacher/bank' }) }
function goAudit() { uni.navigateTo({ url: '/pages/teacher/audit' }) }
function goCreateMission() { uni.navigateTo({ url: '/pages/teacher/mission-create' }) }
function goClasses() { uni.navigateTo({ url: '/pages/teacher/my-classes' }) }

async function handleLogout() {
  uni.showModal({
    title: '确认退出', content: '确定要退出登录吗？',
    success: async (res) => {
      if (res.confirm) {
        try { await authApi.logout() } catch {}
        userStore.logout()
        uni.reLaunch({ url: '/pages/login/index' })
      }
    }
  })
}
</script>

<style scoped>
.favorites { display: flex; min-height: 100vh; background: #f0f2f5; }
.sidebar { width: 240px; background: #fff; box-shadow: 2px 0 8px rgba(0,0,0,0.06); display: flex; flex-direction: column; position: fixed; left: 0; top: 0; bottom: 0; z-index: 10; }
.sidebar-logo { padding: 30rpx 24rpx; font-size: 32rpx; font-weight: bold; color: #409eff; border-bottom: 1rpx solid #f0f0f0; }
.sidebar-user { padding: 24rpx; border-bottom: 1rpx solid #f0f0f0; }
.user-name { font-size: 26rpx; font-weight: bold; color: #333; display: block; }
.user-role { font-size: 22rpx; color: #999; margin-top: 4rpx; display: block; }
.nav-items { padding: 16rpx 0; flex: 1; }
.nav-item { display: flex; align-items: center; padding: 16rpx 24rpx; cursor: pointer; transition: background 0.2s; }
.nav-item:hover { background: #f5f5f5; }
.nav-item.active { background: #ecf5ff; color: #409eff; }
.nav-icon { font-size: 32rpx; margin-right: 12rpx; }
.nav-text { font-size: 26rpx; color: #333; }
.nav-logout:hover { background: #fff0f0; }
.nav-logout .nav-icon { opacity: 0.7; }
.nav-logout .nav-text { color: #e74c3c; }
.nav-group-title { padding: 8rpx 24rpx; font-size: 20rpx; color: #999; font-weight: bold; }

.main { margin-left: 240px; flex: 1; padding: 30rpx 40rpx; }
.panel { background: #fff; border-radius: 12rpx; padding: 20rpx; }
.panel-title { font-size: 28rpx; font-weight: bold; color: #333; padding: 10rpx 0 20rpx; border-bottom: 1rpx solid #f0f0f0; margin-bottom: 16rpx; }

.empty { text-align: center; padding: 80rpx; color: #999; font-size: 26rpx; }
.loading { text-align: center; padding: 40rpx; color: #409eff; font-size: 24rpx; }

.question-table { }
.table-header { display: flex; padding: 16rpx 8rpx; background: #f5f5f5; border-radius: 8rpx; font-size: 22rpx; font-weight: bold; color: #666; }
.table-row { display: flex; padding: 16rpx 8rpx; border-bottom: 1rpx solid #f0f0f0; font-size: 22rpx; align-items: center; }
.table-row:hover { background: #fafafa; }
.col { flex: 1; text-align: center; }
.col-no { flex: 0.8; }
.col-source { flex: 1.5; }
.col-diff { flex: 0.8; }
.col-kp { flex: 0.6; }
.col-action { flex: 1; }

.btn-remove { display: inline-block; padding: 8rpx 16rpx; background: #e74c3c; color: #fff; border-radius: 8rpx; font-size: 20rpx; cursor: pointer; }
.btn-remove:hover { background: #c0392b; }

@media (max-width: 768px) {
  .sidebar { width: 60px; }
  .sidebar-user, .nav-text, .nav-group-title { display: none; }
  .nav-item { justify-content: center; padding: 16rpx 0; }
  .nav-icon { margin-right: 0; }
  .main { margin-left: 60px; }
}
</style>
```

- [ ] **Step 2: Commit**

```bash
cd D:\workspace\code\qidi
git add front/uniapp/src/pages/teacher/favorites.vue
git commit -m "feat: add favorites.vue my favorites page

- Shows list of favorited questions in table format
- Cancel favorite button with confirmation modal
- Sidebar navigation with 我的精选 active

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 前端 — 更新所有 teacher 页面 sidebar

**Files:** Modify all existing teacher pages' sidebar navigation.

需要对以下每个页面的 sidebar 做相同修改：
- `workbench.vue`
- `import.vue`
- `audit.vue`
- `my-classes.vue`
- `class-create.vue`
- `class-edit.vue`
- `class-detail.vue`
- `class-requests.vue`
- `question-edit.vue`
- `mission-create.vue`
- `mission-detail.vue`

- [ ] **Step 1: 修改 workbench.vue 的 sidebar**

找到 workbench.vue 中的 `.nav-items` 部分，替换为：

```vue
      <view class="nav-items">
        <view class="nav-item active" @click="goImport">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">工作台</text>
        </view>
        <view class="nav-group">
          <view class="nav-group-title">题库管理</view>
          <view class="nav-item" @click="goBank">
            <text class="nav-icon">&#128218;</text>
            <text class="nav-text">题库列表</text>
          </view>
          <view class="nav-item" @click="goFavorites">
            <text class="nav-icon">&#11088;</text>
            <text class="nav-text">我的精选</text>
          </view>
        </view>
        <view class="nav-item" @click="goAudit">
          <text class="nav-icon">&#128269;</text>
          <text class="nav-text">OCR审核</text>
        </view>
        <view class="nav-item" @click="goCreateMission">
          <text class="nav-icon">&#128203;</text>
          <text class="nav-text">创建任务</text>
        </view>
        <view class="nav-item" @click="goClasses">
          <text class="nav-icon">&#127963;</text>
          <text class="nav-text">班级管理</text>
        </view>
        <view class="nav-item nav-logout" @click="handleLogout">
          <text class="nav-icon">&#128682;</text>
          <text class="nav-text">退出登录</text>
        </view>
      </view>
```

在 script 部分添加导航函数：

```typescript
function goBank() { uni.navigateTo({ url: '/pages/teacher/bank' }) }
function goFavorites() { uni.navigateTo({ url: '/pages/teacher/favorites' }) }
```

在 CSS 部分添加：

```css
.nav-group { margin-bottom: 8rpx; }
.nav-group-title { padding: 8rpx 24rpx; font-size: 20rpx; color: #999; font-weight: bold; }
```

- [ ] **Step 2: 修改其他 teacher 页面**

对以下每个页面重复 Step 1 的 sidebar 修改（调整 `active` 状态对应的 nav-item）：
- `import.vue` — "题库列表" 为 active
- `audit.vue` — "OCR审核" 为 active
- `my-classes.vue` — "班级管理" 为 active
- 其他 class/mission 页面 — 对应 item 为 active

每个页面需要：
1. 替换 `.nav-items` 内容为新的菜单结构
2. 添加 `goBank` 和 `goFavorites` 导航函数
3. 添加 `.nav-group` 和 `.nav-group-title` CSS

- [ ] **Step 3: Commit**

```bash
cd D:\workspace\code\qidi
git add front/uniapp/src/pages/teacher/
git commit -m "feat: update all teacher page sidebars with new navigation

- 题库导入 renamed to 题库管理 (group)
- Added 题库列表 and 我的精选 under 题库管理 group
- Updated navigation in all 11 teacher pages

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: 数据库迁移 + 部署

- [ ] **Step 1: 运行数据库迁移**

```bash
cd D:\workspace\code\qidi\tiku
python manage.py migrate review
```

Expected output: `Running migrations: Applying review.0XXX_add_teacher_favorite... OK`

- [ ] **Step 2: 验证 API 端点**

```bash
cd D:\workspace\code\qidi\tiku
python manage.py runserver
```

Then test:
- `GET http://localhost:8000/api/v1/teacher/knowledge-tree/` (需登录)
- `POST http://localhost:8000/api/v1/teacher/favorites/add/` (body: `{"question_id": 1}`)
- `GET http://localhost:8000/api/v1/teacher/favorites/`

- [ ] **Step 3: Commit**

```bash
cd D:\workspace\code\qidi
git add -A
git status
# Verify only expected files are staged
```

---

## Self-Review Checklist

1. **Spec coverage**: All requirements from design doc covered?
   - ✅ Menu rename: 题库导入 → 题库管理 (Task 6)
   - ✅ New "我的精选" sub-item (Task 4, 5, 6)
   - ✅ Knowledge tree in bank.vue (Task 4)
   - ✅ Question list table (Task 4)
   - ✅ Add to favorite button (Task 4)
   - ✅ Favorites page (Task 5)
   - ✅ Backend model + API (Task 1, 2)
   - ✅ Teacher stage field — noted but deferred (needs admin UI)

2. **Placeholder scan**: No TBD/TODO found

3. **Type consistency**: 
   - `Favorite` interface in favorites.ts matches `FavoriteSerializer` fields
   - `knowledgeApi.getTree` returns `KnowledgeTree` matching API response format
   - `difficultyText` function consistent across bank.vue and favorites.vue