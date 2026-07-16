<template>
  <view class="course-list">
    <TeacherSidebar activeItem="course-list" />

    <view class="main">
      <!-- Header with create button -->
      <view class="page-header">
        <text class="page-title">课程管理</text>
        <button class="create-btn" @click="showCreateDialog = true">+ 新建课程</button>
      </view>

      <!-- Loading state -->
      <view v-if="loading" class="loading">
        <text>加载中...</text>
      </view>

      <!-- Empty state -->
      <view v-else-if="courses.length === 0" class="empty">
        <text class="empty-icon">📚</text>
        <text class="empty-text">暂无课程，点击右上角「新建课程」开始创建</text>
      </view>

      <!-- Card grid -->
      <view v-else class="card-grid">
        <CourseCard
          v-for="course in courses"
          :key="course.id"
          :course="course"
          @click="handleCourseClick"
          @materials="handleMaterials"
          @practice="handlePractice"
          @delete="handleDeleteConfirm"
        />
      </view>
    </view>

    <!-- Create course dialog -->
    <view v-if="showCreateDialog" class="modal-overlay" @click.self="closeCreateDialog">
      <view class="modal">
        <text class="modal-title">新建课程</text>
        <view class="form-group">
          <text class="form-label">课程名称 <text class="required">*</text></text>
          <input
            class="form-input"
            v-model="createForm.name"
            placeholder="请输入课程名称"
            maxlength="50"
          />
        </view>
        <view class="form-row">
          <view class="form-group half">
            <text class="form-label">学科 <text class="required">*</text></text>
            <select v-model="createForm.subject" class="form-select">
              <option value="" disabled>请选择学科</option>
              <option v-for="s in subjectOptions" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
          </view>
          <view class="form-group half">
            <text class="form-label">年级 <text class="required">*</text></text>
            <select v-model="createForm.grade_level" class="form-select">
              <option value="" disabled>请选择年级</option>
              <option v-for="g in gradeOptions" :key="g.value" :value="g.value">{{ g.label }}</option>
            </select>
          </view>
        </view>
        <view class="form-group">
          <text class="form-label">课程简介</text>
          <textarea
            class="form-textarea"
            v-model="createForm.description"
            placeholder="请输入课程简介（选填）"
            maxlength="200"
          />
        </view>
        <view class="modal-footer">
          <button size="default" @click="closeCreateDialog">取消</button>
          <button size="default" type="primary" @click="handleCreate" :disabled="creating">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </view>
      </view>
    </view>

    <!-- Delete confirmation dialog -->
    <view v-if="deleteDialogVisible" class="modal-overlay" @click.self="deleteDialogVisible = false">
      <view class="modal delete-modal">
        <text class="modal-title">确认删除</text>
        <text class="delete-warning">确定要删除课程「{{ courseToDelete?.name }}」吗？此操作不可撤销。</text>
        <view class="modal-footer">
          <button size="default" @click="deleteDialogVisible = false">取消</button>
          <button size="default" type="warn" @click="handleDelete" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import CourseCard from '@/components/CourseCard.vue'
import { courseApi } from '@/api/courses'

// ============================================================
// Course list
// ============================================================
interface Course {
  id: number
  name: string
  description?: string
  subject: string
  grade_level: string
  material_count?: number
  question_count?: number
}

const courses = ref<Course[]>([])
const loading = ref(false)

async function loadCourses() {
  loading.value = true
  try {
    const res = await courseApi.list()
    courses.value = res.data || []
  } catch (e: any) {
    console.error('加载课程列表失败:', e)
    // 401 错误 courseFetch 已处理跳转登录，这里只处理其他错误
    if (!e.message?.includes('401') && !e.message?.includes('登录')) {
      uni.showToast({ title: '加载失败，请重试', icon: 'none' })
    }
  } finally {
    loading.value = false
  }
}

// ============================================================
// Card actions
// ============================================================
function handleCourseClick(course: Course) {
  uni.navigateTo({
    url: `/pages/teacher/course-detail?id=${course.id}`,
    fail: () => uni.showToast({ title: '课程详情页开发中', icon: 'none' }),
  })
}

function handleMaterials(course: Course) {
  uni.navigateTo({
    url: `/pages/teacher/course-materials?id=${course.id}`,
    fail: () => uni.showToast({ title: '课程资料页开发中', icon: 'none' }),
  })
}

function handlePractice(course: Course) {
  uni.navigateTo({
    url: `/pages/teacher/course-practice?id=${course.id}`,
    fail: () => uni.showToast({ title: '课程练习页开发中', icon: 'none' }),
  })
}

// ============================================================
// Create dialog
// ============================================================
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({ name: '', subject: '', grade_level: '', description: '' })

const subjectOptions = [
  { value: '数学', label: '数学' },
  { value: '语文', label: '语文' },
  { value: '英语', label: '英语' },
  { value: '物理', label: '物理' },
  { value: '化学', label: '化学' },
  { value: '生物', label: '生物' },
  { value: '历史', label: '历史' },
  { value: '地理', label: '地理' },
  { value: '政治', label: '政治' },
]

const gradeOptions = [
  { value: '一年级', label: '一年级' },
  { value: '二年级', label: '二年级' },
  { value: '三年级', label: '三年级' },
  { value: '四年级', label: '四年级' },
  { value: '五年级', label: '五年级' },
  { value: '六年级', label: '六年级' },
  { value: '七年级', label: '七年级' },
  { value: '八年级', label: '八年级' },
  { value: '九年级', label: '九年级' },
  { value: '高一', label: '高一' },
  { value: '高二', label: '高二' },
  { value: '高三', label: '高三' },
]

function closeCreateDialog() {
  showCreateDialog.value = false
  createForm.value = { name: '', subject: '', grade_level: '', description: '' }
}

async function handleCreate() {
  const { name, subject, grade_level } = createForm.value
  if (!name.trim()) {
    uni.showToast({ title: '请输入课程名称', icon: 'none' })
    return
  }
  if (!subject) {
    uni.showToast({ title: '请选择学科', icon: 'none' })
    return
  }
  if (!grade_level) {
    uni.showToast({ title: '请选择年级', icon: 'none' })
    return
  }

  creating.value = true
  try {
    await courseApi.create({
      name: name.trim(),
      subject,
      grade_level,
      description: createForm.value.description.trim() || undefined,
    })
    uni.showToast({ title: '创建成功', icon: 'success' })
    closeCreateDialog()
    await loadCourses()
  } catch (e: any) {
    console.error('创建课程失败:', e)
    const msg = e?.message || ''
    if (msg.includes('401') || msg.includes('登录')) {
      // courseFetch 已处理跳转，这里不重复提示
    } else {
      uni.showToast({ title: msg || '创建失败，请重试', icon: 'none' })
    }
  } finally {
    creating.value = false
  }
}

// ============================================================
// Delete confirmation
// ============================================================
const deleteDialogVisible = ref(false)
const courseToDelete = ref<Course | null>(null)
const deleting = ref(false)

function handleDeleteConfirm(course: Course) {
  courseToDelete.value = course
  deleteDialogVisible.value = true
}

async function handleDelete() {
  if (!courseToDelete.value) return
  deleting.value = true
  try {
    await courseApi.remove(courseToDelete.value.id)
    uni.showToast({ title: '已删除', icon: 'success' })
    deleteDialogVisible.value = false
    courseToDelete.value = null
    await loadCourses()
  } catch (e: any) {
    console.error('删除课程失败:', e)
    uni.showToast({ title: e?.message || '删除失败，请重试', icon: 'none' })
  } finally {
    deleting.value = false
  }
}

// ============================================================
// Lifecycle
// ============================================================
onMounted(() => {
  loadCourses()
})
</script>

<style scoped>
.course-list {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}

.main {
  margin-left: 240px;
  flex: 1;
  padding: 48rpx;
  overflow: visible;
}

/* Page header */
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24rpx; }
.page-title { font-size: 32rpx; font-weight: 600; color: #303133; }
.create-btn { background: #409eff; color: #fff; border: none; border-radius: 4px; padding: 6px 16px; font-size: 13px; cursor: pointer; }

/* Loading / Empty */
.loading {
  text-align: center;
  color: #909399;
  padding: 120rpx 0;
  font-size: 28rpx;
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 160rpx 0;
}

.empty-icon {
  font-size: 80rpx;
  margin-bottom: 24rpx;
}

.empty-text {
  font-size: 26rpx;
  color: #909399;
}

/* Card grid — 3 per row */
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24rpx;
}

/* Modal overlay */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #fff;
  border-radius: 16rpx;
  padding: 40rpx;
  width: 600rpx;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #303133;
  display: block;
  margin-bottom: 24rpx;
}

/* Form */
.form-group {
  margin-bottom: 20rpx;
}

.form-row {
  display: flex;
  gap: 20rpx;
}

.half {
  flex: 1;
}

.form-label {
  font-size: 24rpx;
  color: #606266;
  display: block;
  margin-bottom: 8rpx;
}

.required {
  color: #f56c6c;
}

.form-input {
  width: 100%;
  height: 64rpx;
  padding: 0 20rpx;
  background: #f5f7fa;
  border-radius: 8rpx;
  font-size: 26rpx;
  color: #303133;
  border: 1rpx solid #e4e7ed;
}

.form-input:focus {
  border-color: #409eff;
  background: #fff;
}

.form-textarea {
  width: 100%;
  height: 120rpx;
  padding: 16rpx 20rpx;
  background: #f5f7fa;
  border-radius: 8rpx;
  font-size: 26rpx;
  color: #303133;
  border: 1rpx solid #e4e7ed;
  box-sizing: border-box;
}

.form-textarea:focus {
  border-color: #409eff;
  background: #fff;
}

.form-select {
  width: 100%;
  height: 64rpx;
  padding: 0 20rpx;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 8rpx;
  font-size: 26rpx;
  color: #303133;
  outline: none;
  box-sizing: border-box;
}

.form-select:focus {
  border-color: #409eff;
  background: #fff;
}

.form-picker {
  width: 100%;
}

.picker-value {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 64rpx;
  padding: 0 20rpx;
  background: #f5f7fa;
  border-radius: 8rpx;
  border: 1rpx solid #e4e7ed;
}

.picker-text {
  font-size: 26rpx;
  color: #303133;
}

.picker-placeholder {
  font-size: 26rpx;
  color: #c0c4cc;
}

.picker-arrow {
  font-size: 16rpx;
  color: #909399;
}

.modal-footer {
  display: flex;
  gap: 16rpx;
  justify-content: flex-end;
  margin-top: 32rpx;
}

.modal-footer button {
  margin: 0;
}

/* Delete modal */
.delete-modal {
  width: 500rpx;
}

.delete-warning {
  font-size: 26rpx;
  color: #606266;
  display: block;
  line-height: 1.6;
  margin-bottom: 24rpx;
}
</style>
