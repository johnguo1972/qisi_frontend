<template>
  <view class="course-materials">
    <TeacherSidebar activeItem="course-list" />

    <view class="main">
      <!-- Breadcrumb + Upload button -->
      <view class="page-header">
        <view class="breadcrumb">
          <text class="breadcrumb-item" @click="goCourseList">课程管理</text>
          <text class="breadcrumb-sep">/</text>
          <text class="breadcrumb-current">{{ courseName }}</text>
          <text class="breadcrumb-sep">/</text>
          <text class="breadcrumb-current">课程资料</text>
        </view>
        <button class="upload-btn" size="small" @click="triggerFileUpload">
          <text class="btn-icon">+</text> 上传资料
        </button>
      </view>

      <!-- Loading state -->
      <view v-if="loading" class="loading">
        <text>加载中...</text>
      </view>

      <!-- Empty state -->
      <view v-else-if="materials.length === 0" class="empty">
        <text class="empty-icon">📁</text>
        <text class="empty-text">暂无资料，点击右上角「上传资料」开始上传</text>
      </view>

      <!-- File list table -->
      <view v-else class="file-table">
        <view class="table-header">
          <text class="col-name">文件名</text>
          <text class="col-type">类型</text>
          <text class="col-size">大小</text>
          <text class="col-date">上传时间</text>
          <text class="col-actions">操作</text>
        </view>
        <view
          v-for="item in materials"
          :key="item.id"
          class="table-row"
        >
          <text class="col-name file-name" :title="item.name || item.file_path">{{ item.name || item.file_path?.split('/').pop() || '未知文件' }}</text>
          <text class="col-type">
            <text :class="['type-badge', fileTypeClass(item.file_type)]">{{ fileTypeLabel(item.file_type) }}</text>
          </text>
          <text class="col-size">{{ formatFileSize(item.file_size) }}</text>
          <text class="col-date">{{ formatDate(item.created_at) }}</text>
          <view class="col-actions">
            <button size="mini" type="primary" @click="handleDownload(item)">下载</button>
            <button size="mini" @click="handlePreview(item)">预览</button>
            <button size="mini" type="warn" @click="handleDeleteConfirm(item)">删除</button>
          </view>
        </view>
      </view>
    </view>

    <!-- Delete confirmation dialog -->
    <view v-if="deleteDialogVisible" class="modal-overlay" @click.self="deleteDialogVisible = false">
      <view class="modal delete-modal">
        <text class="modal-title">确认删除</text>
        <text class="delete-warning">确定要删除资料「{{ materialToDelete?.name }}」吗？此操作不可撤销。</text>
        <view class="modal-footer">
          <button size="default" @click="deleteDialogVisible = false">取消</button>
          <button size="default" type="warn" @click="handleDelete" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </view>
      </view>
    </view>

    <!-- Upload progress dialog -->
    <view v-if="uploading" class="modal-overlay">
      <view class="modal upload-modal">
        <text class="modal-title">上传中...</text>
        <text class="upload-filename">{{ uploadFileName }}</text>
        <view class="progress-bar">
          <view class="progress-fill" :style="{ width: uploadProgress + '%' }"></view>
        </view>
        <text class="progress-text">{{ uploadProgress }}%</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import { materialApi, courseApi } from '@/api/courses'

// ============================================================
// Course info
// ============================================================
const courseId = ref<number>(0)
const courseName = ref<string>('课程资料')

// ============================================================
// Materials list
// ============================================================
interface Material {
  id: number
  name: string
  file_type: string
  file_size: number
  created_at: string
}

const materials = ref<Material[]>([])
const loading = ref(false)

async function loadMaterials() {
  loading.value = true
  try {
    const res = await materialApi.list(courseId.value)
    // courseFetch 返回 {success: true, data: [...]}，所以数组在 res.data.data
    materials.value = res.data?.data || res.data || []
  } catch (e) {
    console.error('加载课程资料失败:', e)
    uni.showToast({ title: '加载失败，请重试', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function loadCourseInfo() {
  try {
    const res = await courseApi.detail(courseId.value)
    if (res.data) {
      courseName.value = res.data.name || courseName.value
    }
  } catch {
    // Use default name if fetch fails
  }
}

// ============================================================
// File upload
// ============================================================
const ALLOWED_TYPES = [
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/bmp',
  'image/webp',
]
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

const uploading = ref(false)
const uploadProgress = ref(0)
const uploadFileName = ref('')

function triggerFileUpload() {
  // #ifdef H5
  // H5 环境：创建临时 input 触发选择
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,.gif,.bmp,.webp'
  input.style.display = 'none'
  input.onchange = (e: Event) => {
    const target = e.target as HTMLInputElement
    const file = target.files?.[0]
    if (file) handleFileSelected(file)
    document.body.removeChild(input)
  }
  document.body.appendChild(input)
  input.click()
  // #endif
  // #ifndef H5
  uni.chooseFile({
    count: 1,
    extension: ['.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg'],
    success: (res) => {
      if (res.tempFiles?.length > 0) {
        handleFileSelected(res.tempFiles[0] as any)
      }
    },
  })
  // #endif
}

function handleFileSelected(file: File | { name: string; size: number; path: string }) {
  const fileName = file.name
  const fileSize = file.size

  // Validate file type by extension
  const ext = fileName.split('.').pop()?.toLowerCase() || ''
  const allowedExts = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']
  if (!allowedExts.includes(ext)) {
    uni.showToast({ title: '不支持的文件类型', icon: 'none' })
    return
  }

  // Validate file size
  if (fileSize > MAX_FILE_SIZE) {
    uni.showToast({ title: '文件大小不能超过 50MB', icon: 'none' })
    return
  }

  // #ifdef H5
  uploadFile(file as File)
  // #endif
  // #ifndef H5
  // 非 H5 环境需要转换文件
  uni.showToast({ title: '请使用 H5 浏览器上传文件', icon: 'none' })
  // #endif
}

async function uploadFile(file: File) {
  uploading.value = true
  uploadProgress.value = 0
  uploadFileName.value = file.name

  try {
    await materialApi.upload(courseId.value, file)
    uni.showToast({ title: '上传成功', icon: 'success' })
    await loadMaterials()
  } catch (e: any) {
    console.error('上传失败:', e)
    uni.showToast({ title: e?.message || '上传失败，请重试', icon: 'none' })
  } finally {
    uploading.value = false
    uploadProgress.value = 100
  }
}

// ============================================================
// Download
// ============================================================
function handleDownload(item: Material) {
  const url = materialApi.download(courseId.value, item.id)
  const a = document.createElement('a')
  a.href = url
  a.download = item.name
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

// ============================================================
// Preview
// ============================================================
async function handlePreview(item: Material) {
  try {
    // 直接打开预览 URL，后端会通过 FileResponse 返回文件内容
    const previewUrl = `/api/v1/courses/${courseId.value}/materials/${item.id}/preview/`
    const token = uni.getStorageSync('accessToken')
    const fullUrl = `${window.location.origin}${previewUrl}`
    window.open(fullUrl, '_blank')
  } catch (e) {
    console.error('预览失败:', e)
    uni.showToast({ title: '预览失败，请重试', icon: 'none' })
  }
}

// ============================================================
// Delete
// ============================================================
const deleteDialogVisible = ref(false)
const materialToDelete = ref<Material | null>(null)
const deleting = ref(false)

function handleDeleteConfirm(item: Material) {
  materialToDelete.value = item
  deleteDialogVisible.value = true
}

async function handleDelete() {
  if (!materialToDelete.value) return
  deleting.value = true
  try {
    await materialApi.remove(courseId.value, materialToDelete.value.id)
    uni.showToast({ title: '已删除', icon: 'success' })
    deleteDialogVisible.value = false
    materialToDelete.value = null
    await loadMaterials()
  } catch (e: any) {
    console.error('删除资料失败:', e)
    uni.showToast({ title: e?.message || '删除失败，请重试', icon: 'none' })
  } finally {
    deleting.value = false
  }
}

// ============================================================
// Helpers
// ============================================================
function formatFileSize(bytes: number): string {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB'
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const min = String(d.getMinutes()).padStart(2, '0')
    return `${y}-${m}-${day} ${h}:${min}`
  } catch {
    return dateStr
  }
}

function fileTypeLabel(type: string): string {
  if (!type) return '未知'
  if (type.includes('pdf')) return 'PDF'
  if (type.includes('word') || type.includes('doc')) return 'Word'
  if (type.includes('sheet') || type.includes('xls')) return 'Excel'
  if (type.includes('presentation') || type.includes('ppt')) return 'PPT'
  if (type.startsWith('image/')) return '图片'
  return type.split('/')[1]?.toUpperCase() || '未知'
}

function fileTypeClass(type: string): string {
  if (!type) return ''
  if (type.includes('pdf')) return 'type-pdf'
  if (type.includes('word') || type.includes('doc')) return 'type-word'
  if (type.includes('sheet') || type.includes('xls')) return 'type-excel'
  if (type.includes('presentation') || type.includes('ppt')) return 'type-ppt'
  if (type.startsWith('image/')) return 'type-image'
  return ''
}

// ============================================================
// Navigation
// ============================================================
function goCourseList() {
  uni.navigateTo({
    url: '/pages/teacher/course-list',
    fail: () => uni.showToast({ title: '返回课程列表失败', icon: 'none' }),
  })
}

// ============================================================
// Lifecycle
// ============================================================
onMounted(() => {
  // Get course ID from URL parameters
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1] as any
  const options = currentPage.options || {}
  const id = Number(options.id)

  if (!id) {
    uni.showToast({ title: '缺少课程ID参数', icon: 'none' })
    return
  }

  courseId.value = id
  loadCourseInfo()
  loadMaterials()
})
</script>

<style scoped>
.course-materials {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}

.main {
  margin-left: 240px;
  flex: 1;
  padding: 24rpx;
}

/* ============================================================
   Page header with breadcrumb
   ============================================================ */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24rpx;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8rpx;
  font-size: 24rpx;
}

.breadcrumb-item {
  color: #909399;
  cursor: pointer;
  transition: color 0.2s;
}

.breadcrumb-item:hover {
  color: #409eff;
}

.breadcrumb-sep {
  color: #c0c4cc;
}

.breadcrumb-current {
  color: #303133;
  font-weight: 500;
}

.upload-btn {
  margin: 0;
  font-size: 26rpx;
  padding: 8rpx 24rpx;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  display: flex;
  align-items: center;
  gap: 4rpx;
}

.upload-btn::after {
  border: none;
}

.btn-icon {
  font-size: 30rpx;
  font-weight: 300;
}

.hidden-input {
  display: none;
}

/* ============================================================
   Loading / Empty
   ============================================================ */
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

/* ============================================================
   File table
   ============================================================ */
.file-table {
  background: #fff;
  border-radius: 12rpx;
  overflow: hidden;
}

.table-header {
  display: flex;
  align-items: center;
  padding: 16rpx 24rpx;
  background: #f5f7fa;
  font-size: 24rpx;
  color: #909399;
  font-weight: 500;
}

.table-row {
  display: flex;
  align-items: center;
  padding: 16rpx 24rpx;
  border-bottom: 1rpx solid #f0f0f0;
  font-size: 26rpx;
  color: #303133;
}

.table-row:last-child {
  border-bottom: none;
}

.table-row:hover {
  background: #fafafa;
}

.col-name {
  flex: 2;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-name {
  cursor: default;
}

.col-type {
  width: 100rpx;
  text-align: center;
}

.col-size {
  width: 120rpx;
  text-align: right;
  color: #606266;
  font-size: 24rpx;
}

.col-date {
  width: 260rpx;
  text-align: center;
  color: #909399;
  font-size: 24rpx;
}

.col-actions {
  width: 280rpx;
  display: flex;
  gap: 8rpx;
  justify-content: center;
}

.col-actions button {
  margin: 0;
  font-size: 22rpx;
  padding: 4rpx 16rpx;
}

/* Type badges */
.type-badge {
  display: inline-block;
  padding: 4rpx 12rpx;
  border-radius: 6rpx;
  font-size: 22rpx;
  font-weight: 500;
}

.type-pdf {
  background: #fef0f0;
  color: #f56c6c;
}

.type-word {
  background: #ecf5ff;
  color: #409eff;
}

.type-excel {
  background: #f0f9eb;
  color: #67c23a;
}

.type-ppt {
  background: #fdf6ec;
  color: #e6a23c;
}

.type-image {
  background: #f4f4f5;
  color: #909399;
}

/* ============================================================
   Modals
   ============================================================ */
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
  width: 500rpx;
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

/* Upload progress modal */
.upload-modal {
  width: 400rpx;
  text-align: center;
}

.upload-filename {
  font-size: 24rpx;
  color: #606266;
  display: block;
  margin-bottom: 24rpx;
  word-break: break-all;
}

.progress-bar {
  width: 100%;
  height: 12rpx;
  background: #e4e7ed;
  border-radius: 6rpx;
  overflow: hidden;
  margin-bottom: 12rpx;
}

.progress-fill {
  height: 100%;
  background: #409eff;
  border-radius: 6rpx;
  transition: width 0.3s;
}

.progress-text {
  font-size: 24rpx;
  color: #909399;
}
</style>
