<template>
  <view class="course-detail">
    <TeacherSidebar activeItem="course-list" @navigate="handleSidebarNavigate" />

    <view class="main">
      <view class="page-header">
        <view class="header-title">
          <button class="back-btn" @click="goBack">返回课程管理</button>
          <view class="title-stack">
            <text class="eyebrow">课程管理</text>
            <text class="page-title">{{ course?.name || '课程详情' }}</text>
          </view>
        </view>
        <view v-if="course" class="header-actions">
          <button class="btn secondary" @click="openEdit">编辑课程</button>
          <button class="btn secondary" @click="goMaterials">课程资料</button>
          <button class="btn primary" @click="goPractice">课程练习</button>
        </view>
      </view>

      <view v-if="loading" class="loading-card">
        <text>正在加载课程详情...</text>
      </view>

      <view v-else-if="errorMessage" class="error-card">
        <text class="error-title">课程详情加载失败</text>
        <text class="error-message">{{ errorMessage }}</text>
        <view class="error-actions">
          <button class="btn secondary" @click="loadCourse">重新加载</button>
          <button class="btn primary" @click="goBack">返回课程管理</button>
        </view>
      </view>

      <template v-else-if="course">
        <view class="course-hero">
          <view class="hero-cover" :style="{ background: subjectGradient }">
            <text class="subject-icon">{{ subjectIcon }}</text>
            <text class="grade-badge">{{ course.grade_level || '未设置年级' }}</text>
          </view>
          <view class="hero-content">
            <view class="hero-heading">
              <view>
                <text class="hero-title">{{ course.name }}</text>
                <text class="hero-meta">{{ subjectText(course.subject) || '未设置学科' }} · {{ course.grade_level || '未设置年级' }}</text>
              </view>
              <text class="owner-name">创建教师：{{ course.teacher_name || '当前教师' }}</text>
            </view>
            <text class="description">{{ course.description || '暂无课程简介' }}</text>
            <view class="date-row">
              <text>创建于 {{ formatDate(course.created_at) }}</text>
              <text v-if="course.updated_at">最近更新 {{ formatDate(course.updated_at) }}</text>
            </view>
          </view>
        </view>

        <view class="stats-grid">
          <view class="stat-card">
            <text class="stat-icon">📁</text>
            <view>
              <text class="stat-label">课程资料</text>
              <text class="stat-value">{{ course.material_count ?? 0 }}</text>
            </view>
          </view>
          <view class="stat-card">
            <text class="stat-icon">📝</text>
            <view>
              <text class="stat-label">课程习题</text>
              <text class="stat-value">{{ course.question_count ?? 0 }}</text>
            </view>
          </view>
          <view class="stat-card">
            <text class="stat-icon">🌳</text>
            <view>
              <text class="stat-label">目录节点</text>
              <text class="stat-value">{{ flattenedTree.length }}</text>
            </view>
          </view>
        </view>

        <view class="content-grid">
          <view class="panel directory-panel">
            <view class="panel-header">
              <view>
                <text class="panel-title">课程目录</text>
                <text class="panel-subtitle">按课程目录组织习题内容</text>
              </view>
              <button class="link-btn" @click="goPractice">管理目录</button>
            </view>
            <view v-if="flattenedTree.length" class="directory-list">
              <view v-for="node in flattenedTree" :key="node.id" class="directory-row">
                <text class="directory-mark">{{ node.depth === 0 ? '▣' : '•' }}</text>
                <text class="directory-name" :style="{ paddingLeft: `${node.depth * 28}rpx` }">{{ node.name }}</text>
              </view>
            </view>
            <view v-else class="empty-panel">
              <text class="empty-icon">🌳</text>
              <text>暂无课程目录</text>
              <button class="btn primary empty-action" @click="goPractice">去创建目录</button>
            </view>
          </view>

          <view class="panel actions-panel">
            <view class="panel-header">
              <view>
                <text class="panel-title">课程操作</text>
                <text class="panel-subtitle">继续完成课程内容建设</text>
              </view>
            </view>
            <view class="action-list">
              <view class="action-item" @click="goMaterials">
                <text class="action-icon">📁</text>
                <view class="action-copy">
                  <text class="action-title">课程资料</text>
                  <text class="action-desc">上传、预览资料并从资料导入习题</text>
                </view>
                <text class="action-arrow">›</text>
              </view>
              <view class="action-item" @click="goPractice">
                <text class="action-icon">📝</text>
                <view class="action-copy">
                  <text class="action-title">课程练习</text>
                  <text class="action-desc">管理课程习题、目录和布置作业</text>
                </view>
                <text class="action-arrow">›</text>
              </view>
              <view class="action-item" @click="openEdit">
                <text class="action-icon">✏️</text>
                <view class="action-copy">
                  <text class="action-title">编辑课程信息</text>
                  <text class="action-desc">修改课程名称、学科、年级和简介</text>
                </view>
                <text class="action-arrow">›</text>
              </view>
            </view>
          </view>
        </view>
      </template>
    </view>

    <view v-if="editVisible" class="modal-overlay" @click.self="closeEdit">
      <view class="modal">
        <text class="modal-title">编辑课程信息</text>
        <view class="form-group">
          <text class="form-label">课程名称 <text class="required">*</text></text>
          <input v-model="editForm.name" class="form-input" maxlength="200" placeholder="请输入课程名称" />
        </view>
        <view class="form-row">
          <view class="form-group half">
            <text class="form-label">学科 <text class="required">*</text></text>
            <picker :range="subjectOptions" @change="onSubjectChange">
              <view class="form-select">{{ subjectText(editForm.subject) || '请选择学科' }}</view>
            </picker>
          </view>
          <view class="form-group half">
            <text class="form-label">年级 <text class="required">*</text></text>
            <picker :range="gradeOptions" @change="onGradeChange">
              <view class="form-select">{{ editForm.grade_level || '请选择年级' }}</view>
            </picker>
          </view>
        </view>
        <view class="form-group">
          <text class="form-label">课程简介</text>
          <textarea v-model="editForm.description" class="form-textarea" maxlength="500" placeholder="请输入课程简介（选填）" />
        </view>
        <view class="modal-footer">
          <button class="btn secondary" @click="closeEdit">取消</button>
          <button class="btn primary" :disabled="saving" @click="saveCourse">{{ saving ? '保存中...' : '保存' }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import { courseApi, treeApi } from '@/api/courses'
import { navigateRoleSection } from '@/utils/role-navigation'

interface Course {
  id: string
  name: string
  description?: string
  subject?: string
  grade_level?: string
  teacher_name?: string
  material_count?: number
  question_count?: number
  created_at?: string
  updated_at?: string
}

interface TreeNode {
  id: string
  name: string
  children?: TreeNode[]
}

interface FlatTreeNode extends TreeNode {
  depth: number
}

const TEACHER_ROUTES: Record<string, string> = {
  workbench: '/pages/teacher/layout',
  'question-bank': '/pages/teacher/question-bank',
  favorites: '/pages/teacher/favorites',
  'student-management': '/pages/teacher/my-classes',
  'assignment-list': '/pages/teacher/mission-list',
  'learning-stats': '/pages/teacher/learning-stats',
  'course-list': '/pages/teacher/course-list',
}

const courseId = ref('')
const course = ref<Course | null>(null)
const treeNodes = ref<TreeNode[]>([])
const loading = ref(false)
const errorMessage = ref('')
const editVisible = ref(false)
const saving = ref(false)
const editForm = reactive({ name: '', subject: '', grade_level: '', description: '' })

const SUBJECT_CODE_BY_LABEL: Record<string, string> = {
  '\u6570\u5b66': 'math', '\u8bed\u6587': 'chinese', '\u82f1\u8bed': 'english', '\u7269\u7406': 'physics',
  '\u5316\u5b66': 'chemistry', '\u751f\u7269': 'biology', '\u5386\u53f2': 'history', '\u5730\u7406': 'geography',
}

function canonicalSubject(value: string) {
  return SUBJECT_CODE_BY_LABEL[value] || value
}

function subjectText(value?: string) {
  if (!value) return ''
  return Object.entries(SUBJECT_CODE_BY_LABEL).find(([, code]) => code === value)?.[0] || value
}

const subjectOptions = ['数学', '语文', '英语', '物理', '化学', '生物', '历史', '地理', '政治']
const gradeOptions = [
  '一年级', '二年级', '三年级', '四年级', '五年级', '六年级',
  '七年级', '八年级', '九年级', '高一', '高二', '高三',
]

const flattenedTree = computed<FlatTreeNode[]>(() => {
  const result: FlatTreeNode[] = []
  function walk(nodes: TreeNode[], depth: number) {
    for (const node of nodes) {
      result.push({ ...node, depth })
      if (node.children?.length) walk(node.children, depth + 1)
    }
  }
  walk(treeNodes.value, 0)
  return result
})

const subjectGradient = computed(() => {
  const colors: Record<string, [string, string]> = {
    数学: ['#667eea', '#764ba2'], 语文: ['#f093fb', '#f5576c'], 英语: ['#4facfe', '#00f2fe'],
    物理: ['#43e97b', '#38f9d7'], 化学: ['#fa709a', '#fee140'], 生物: ['#a8edea', '#fed6e3'],
    历史: ['#d299c2', '#fef9d7'], 地理: ['#89f7fe', '#66a6ff'], 政治: ['#ffecd2', '#fcb69f'],
  }
  const canonicalColors: Record<string, [string, string]> = {
    math: ['#667eea', '#764ba2'], chinese: ['#f093fb', '#f5576c'], english: ['#4facfe', '#00f2fe'],
    physics: ['#43e97b', '#38f9d7'], chemistry: ['#fa709a', '#fee140'], biology: ['#a8edea', '#fed6e3'],
    history: ['#d299c2', '#fef9d7'], geography: ['#89f7fe', '#66a6ff'],
  }
  const selected = canonicalColors[course.value?.subject || ''] || colors[course.value?.subject || ''] || ['#667eea', '#764ba2']
  return `linear-gradient(135deg, ${selected[0]}, ${selected[1]})`
})

const subjectIcon = computed(() => ({
  数学: '📐', 语文: '📖', 英语: '🔤', 物理: '⚡', 化学: '🧪', 生物: '🧬',
  历史: '📜', 地理: '🌍', 政治: '⚖️',
}[course.value?.subject || ''] || '📚'))

function responseData(response: any): any {
  return response?.data?.data ?? response?.data ?? response
}

async function loadCourse() {
  if (!courseId.value) {
    errorMessage.value = '缺少课程ID参数，请从课程管理列表进入。'
    return
  }

  loading.value = true
  errorMessage.value = ''
  try {
    const response = await courseApi.detail(courseId.value)
    const data = responseData(response)
    if (!data?.id) throw new Error('课程不存在或已被删除')
    course.value = data

    try {
      const treeResponse = await treeApi.list(courseId.value)
      treeNodes.value = responseData(treeResponse) || []
    } catch (treeError) {
      // 详情仍可展示；目录失败单独提示，避免一个附属接口导致整个详情页空白。
      console.error('加载课程目录失败:', treeError)
      treeNodes.value = []
      uni.showToast({ title: '课程目录加载失败', icon: 'none' })
    }
  } catch (error: any) {
    console.error('加载课程详情失败:', error)
    errorMessage.value = error?.message || '课程详情加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function handleSidebarNavigate(page: string) {
  // #ifndef MP-WEIXIN
  navigateRoleSection('teacher', page)
  // #endif
  // #ifdef MP-WEIXIN
  const url = TEACHER_ROUTES[page]
  if (url) uni.redirectTo({ url })
  // #endif
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
  } else {
    uni.redirectTo({ url: '/pages/teacher/course-list' })
  }
}

function goMaterials() {
  uni.navigateTo({ url: `/pages/teacher/course-materials?id=${courseId.value}` })
}

function goPractice() {
  uni.navigateTo({ url: `/pages/teacher/course-practice?id=${courseId.value}` })
}

function openEdit() {
  if (!course.value) return
  editForm.name = course.value.name || ''
  editForm.subject = course.value.subject || ''
  editForm.grade_level = course.value.grade_level || ''
  editForm.description = course.value.description || ''
  editVisible.value = true
}

function closeEdit() {
  if (!saving.value) editVisible.value = false
}

function onSubjectChange(event: any) {
  editForm.subject = canonicalSubject(subjectOptions[Number(event.detail.value)] || '')
}

function onGradeChange(event: any) {
  editForm.grade_level = gradeOptions[Number(event.detail.value)] || ''
}

async function saveCourse() {
  if (!editForm.name.trim()) {
    uni.showToast({ title: '请输入课程名称', icon: 'none' })
    return
  }
  if (!editForm.subject || !editForm.grade_level) {
    uni.showToast({ title: '请选择学科和年级', icon: 'none' })
    return
  }

  saving.value = true
  try {
    const response = await courseApi.update(courseId.value, {
      name: editForm.name.trim(),
      subject: editForm.subject,
      grade_level: editForm.grade_level,
      description: editForm.description.trim(),
    })
    const data = responseData(response)
    course.value = { ...course.value!, ...data }
    editVisible.value = false
    uni.showToast({ title: '课程信息已保存', icon: 'success' })
  } catch (error: any) {
    console.error('保存课程信息失败:', error)
    uni.showToast({ title: error?.message || '保存失败，请重试', icon: 'none' })
  } finally {
    saving.value = false
  }
}

function formatDate(value?: string) {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

onLoad((options: any) => {
  courseId.value = String(options?.id || '')
  loadCourse()
})
</script>

<style scoped>
.course-detail {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}

.main {
  margin-left: 240px;
  flex: 1;
  min-width: 0;
  padding: 30rpx 40rpx 60rpx;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  margin-bottom: 28rpx;
}

.header-title,
.header-actions,
.hero-heading,
.date-row,
.error-actions {
  display: flex;
  align-items: center;
}

.header-title { gap: 20rpx; min-width: 0; }
.title-stack { display: flex; flex-direction: column; min-width: 0; }
.eyebrow { font-size: 22rpx; color: #909399; margin-bottom: 6rpx; }
.page-title { font-size: 36rpx; font-weight: 600; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.header-actions { gap: 12rpx; flex-wrap: wrap; justify-content: flex-end; }

.back-btn,
.btn,
.link-btn {
  border: none;
  border-radius: 8rpx;
  font-size: 24rpx;
  cursor: pointer;
}

.back-btn { margin: 0; padding: 12rpx 18rpx; color: #606266; background: #fff; border: 1rpx solid #dcdfe6; }
.btn { margin: 0; padding: 12rpx 24rpx; line-height: 1.4; }
.btn::after, .back-btn::after { border: none; }
.btn.primary { color: #fff; background: #409eff; }
.btn.secondary { color: #606266; background: #fff; border: 1rpx solid #dcdfe6; }
.link-btn { padding: 8rpx 0; color: #409eff; background: transparent; }

.loading-card,
.error-card,
.course-hero,
.stat-card,
.panel {
  background: #fff;
  border-radius: 12rpx;
  box-shadow: 0 2rpx 10rpx rgba(0, 0, 0, 0.05);
}

.loading-card { padding: 120rpx 20rpx; text-align: center; color: #909399; }
.error-card { padding: 80rpx 30rpx; text-align: center; }
.error-title { display: block; color: #f56c6c; font-size: 30rpx; font-weight: 600; }
.error-message { display: block; margin: 18rpx 0 28rpx; color: #909399; font-size: 24rpx; }
.error-actions { justify-content: center; gap: 16rpx; }

.course-hero { display: flex; overflow: hidden; margin-bottom: 24rpx; }
.hero-cover { position: relative; display: flex; align-items: center; justify-content: center; width: 260rpx; min-height: 230rpx; flex-shrink: 0; }
.subject-icon { font-size: 72rpx; filter: drop-shadow(0 2rpx 4rpx rgba(0, 0, 0, .2)); }
.grade-badge { position: absolute; top: 18rpx; right: 18rpx; padding: 6rpx 14rpx; border-radius: 24rpx; color: #303133; background: rgba(255, 255, 255, .9); font-size: 20rpx; }
.hero-content { flex: 1; min-width: 0; padding: 30rpx 36rpx; }
.hero-heading { justify-content: space-between; gap: 20rpx; }
.hero-title { display: block; color: #303133; font-size: 36rpx; font-weight: 600; }
.hero-meta { display: block; margin-top: 8rpx; color: #409eff; font-size: 24rpx; }
.owner-name { color: #909399; font-size: 22rpx; white-space: nowrap; }
.description { display: block; margin-top: 28rpx; color: #606266; font-size: 26rpx; line-height: 1.7; }
.date-row { gap: 30rpx; margin-top: 24rpx; color: #a0a4aa; font-size: 21rpx; }

.stats-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20rpx; margin-bottom: 24rpx; }
.stat-card { display: flex; align-items: center; gap: 20rpx; padding: 24rpx 28rpx; }
.stat-icon { font-size: 42rpx; }
.stat-label, .stat-value { display: block; }
.stat-label { color: #909399; font-size: 22rpx; }
.stat-value { margin-top: 4rpx; color: #303133; font-size: 38rpx; font-weight: 600; }

.content-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(360rpx, .8fr); gap: 24rpx; }
.panel { min-width: 0; padding: 28rpx; }
.panel-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 20rpx; padding-bottom: 20rpx; border-bottom: 1rpx solid #f0f0f0; }
.panel-title { display: block; color: #303133; font-size: 30rpx; font-weight: 600; }
.panel-subtitle { display: block; margin-top: 8rpx; color: #a0a4aa; font-size: 21rpx; }
.directory-list { padding-top: 10rpx; }
.directory-row { display: flex; align-items: center; min-height: 68rpx; border-bottom: 1rpx solid #f7f7f7; }
.directory-mark { width: 34rpx; color: #409eff; font-size: 22rpx; }
.directory-name { flex: 1; color: #606266; font-size: 25rpx; }
.empty-panel { display: flex; flex-direction: column; align-items: center; padding: 60rpx 0 30rpx; color: #a0a4aa; font-size: 24rpx; }
.empty-icon { margin-bottom: 16rpx; font-size: 48rpx; }
.empty-action { margin-top: 24rpx; }
.action-list { padding-top: 8rpx; }
.action-item { display: flex; align-items: center; gap: 18rpx; padding: 24rpx 4rpx; border-bottom: 1rpx solid #f0f0f0; cursor: pointer; }
.action-item:last-child { border-bottom: none; }
.action-icon { font-size: 36rpx; }
.action-copy { flex: 1; min-width: 0; }
.action-title, .action-desc { display: block; }
.action-title { color: #303133; font-size: 26rpx; font-weight: 500; }
.action-desc { margin-top: 6rpx; color: #909399; font-size: 21rpx; line-height: 1.5; }
.action-arrow { color: #c0c4cc; font-size: 40rpx; font-weight: 300; }

.modal-overlay { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, .5); }
.modal { width: 680rpx; max-width: calc(100vw - 48rpx); box-sizing: border-box; padding: 36rpx; border-radius: 16rpx; background: #fff; }
.modal-title { display: block; margin-bottom: 28rpx; color: #303133; font-size: 32rpx; font-weight: 600; }
.form-row { display: flex; gap: 20rpx; }
.form-group { flex: 1; min-width: 0; margin-bottom: 20rpx; }
.form-label { display: block; margin-bottom: 8rpx; color: #606266; font-size: 24rpx; }
.required { color: #f56c6c; }
.form-input, .form-select, .form-textarea { width: 100%; box-sizing: border-box; border: 1rpx solid #e4e7ed; border-radius: 8rpx; background: #f5f7fa; color: #303133; font-size: 26rpx; }
.form-input { height: 68rpx; padding: 0 20rpx; }
.form-select { display: flex; align-items: center; height: 68rpx; padding: 0 20rpx; }
.form-textarea { display: block; min-height: 140rpx; padding: 16rpx 20rpx; }
.modal-footer { display: flex; justify-content: flex-end; gap: 16rpx; margin-top: 28rpx; }

@media (max-width: 900px) {
  .content-grid { grid-template-columns: 1fr; }
  .hero-heading { align-items: flex-start; flex-direction: column; }
}

@media (max-width: 700px) {
  .main { margin-left: 0; padding: 24rpx; }
  .page-header { align-items: flex-start; flex-direction: column; }
  .header-actions { width: 100%; justify-content: flex-start; }
  .course-hero { flex-direction: column; }
  .hero-cover { width: 100%; min-height: 180rpx; }
  .stats-grid { grid-template-columns: 1fr; }
  .form-row { flex-direction: column; gap: 0; }
}
</style>
