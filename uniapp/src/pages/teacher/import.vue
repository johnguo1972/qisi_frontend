<template>
  <view class="import-page">
    <TeacherSidebar activeItem="import" />

    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">上传试卷</text>
      </view>

      <!-- 上传区域 -->
      <view class="upload-area" @click="chooseFile" :class="{ 'has-file': fileName }">
        <view v-if="!fileName">
          <text class="upload-icon">&#128196;</text>
          <text class="upload-text">点击选择 .docx、.doc 或 .pdf 文件</text>
        </view>
        <view v-else>
          <text class="file-name">&#128206; {{ fileName }}</text>
          <button v-if="!uploading" class="upload-btn" @click.stop="uploadFile">开始导入</button>
          <text v-else class="uploading-text">上传中...</text>
        </view>
      </view>

      <!-- 导入历史 -->
      <view class="history-section">
        <text class="history-title">导入历史</text>
        <view v-if="loading" class="loading">加载中...</view>
        <scroll-view v-else scroll-y class="history-list">
          <view v-for="batch in batches" :key="batch.id" class="batch-card">
            <view class="batch-row">
              <text class="batch-id">#{{ batch.paper_code || batch.id }}</text>
              <view class="batch-meta">
                <text class="batch-title">{{ batch.paper_title || batch.title || '-' }}</text>
                <text class="batch-count" v-if="batch.total_questions">{{ batch.total_questions }} 题</text>
              </view>
              <text class="batch-status" :class="statusClass(batch.task_status || batch.status)">
                {{ statusLabel(batch.task_status || batch.status) }}
              </text>
              <text v-if="batch.progress !== null && batch.progress !== undefined" class="batch-progress">{{ batch.progress }}%</text>
            </view>
            <view class="batch-actions" v-if="(batch.task_status || batch.status) !== 'pending'">
              <button
                v-if="(batch.task_status || batch.status) === 'running'"
                size="mini"
                type="warn"
                @click="handleStopParse(batch.paper)"
              >停止解析</button>
              <button
                v-if="['success', 'failed'].includes(batch.task_status || batch.status)"
                size="mini"
                type="primary"
                @click="handleReparse(batch.paper)"
              >重新解析</button>
              <button
                v-if="(batch.task_status || batch.status) === 'success'"
                size="mini"
                @click="goReviewList(batch.paper)"
              >查看</button>
              <button
                size="mini"
                type="danger"
                class="delete-btn"
                @click="handleDeletePaper(batch.paper, batch.paper_title || '该试卷')"
              >删除</button>
            </view>
          </view>
          <view v-if="batches.length === 0" class="empty-history">
            <text>暂无导入记录</text>
          </view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { questionApi, stopParse, reparsePaper, getParseProgress, deletePaper } from '@/api/questions.ts'
import TeacherSidebar from '@/components/TeacherSidebar.vue'

interface Batch {
  id: number
  paper_id?: number
  paper?: { id: number }
  paper_code?: string
  paper_title?: string
  title?: string
  total_questions?: number
  task_status?: string
  status?: string
  progress?: number
}

const fileName = ref('')
const filePath = ref('')
const uploading = ref(false)
const batches = ref<Batch[]>([])
const loading = ref(false)

const pollingPapers = ref<Set<number>>(new Set())
const pollingTimers = ref<Map<number, ReturnType<typeof setInterval>>>(new Map())

onMounted(async () => {
  loadBatches()
})

onUnmounted(() => {
  clearAllPolling()
})

function chooseFile() {
  uni.chooseFile({
    count: 1,
    extension: ['.docx', '.doc', '.pdf'],
    success: (res) => {
      filePath.value = res.tempFiles[0].path
      fileName.value = res.tempFiles[0].name
    }
  })
}

async function uploadFile() {
  if (!filePath.value) return
  uploading.value = true
  try {
    const res = await questionApi.importFile(filePath.value, fileName.value)
    uni.showToast({ title: '上传成功，开始解析', icon: 'success' })
    const paperId = res.data?.paper_id
    if (paperId) startPolling(paperId)
    fileName.value = ''
    filePath.value = ''
    loadBatches()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '导入失败', icon: 'none' })
  } finally {
    uploading.value = false
  }
}

async function handleStopParse(paperId: number) {
  if (!paperId) return
  try {
    await stopParse(paperId)
    uni.showToast({ title: '已停止解析', icon: 'success' })
    stopPolling(paperId)
    loadBatches()
  } catch (e: any) {
    uni.showToast({ title: e?.message || '停止失败', icon: 'none' })
  }
}

async function handleReparse(paperId: number) {
  if (!paperId) return
  try {
    const res = await reparsePaper(paperId)
    if (res.code === 0 || res.success) {
      uni.showToast({ title: '开始重新解析', icon: 'success' })
      startPolling(paperId)
      loadBatches()
    } else {
      uni.showToast({ title: res.message || '重新解析失败', icon: 'none' })
    }
  } catch (e: any) {
    uni.showToast({ title: e?.message || '重新解析失败', icon: 'none' })
  }
}

async function handleDeletePaper(paperId: number, paperName: string) {
  if (!paperId) return
  uni.showModal({
    title: '确认删除',
    content: `确定要删除"${paperName}"吗？此操作不可恢复。`,
    success: async (res) => {
      if (res.confirm) {
        try {
          const resp = await deletePaper(paperId)
          if (resp.code === 0) {
            uni.showToast({ title: '删除成功', icon: 'success' })
            // Stop polling if this paper was being polled
            stopPolling(paperId)
            loadBatches()
          } else {
            uni.showToast({ title: resp.message || '删除失败', icon: 'none' })
          }
        } catch (e: any) {
          uni.showToast({ title: e?.message || '删除失败', icon: 'none' })
        }
      }
    }
  })
}

function statusClass(status: string): string {
  const map: Record<string, string> = {
    success: 'completed',
    running: 'processing',
    failed: 'failed',
    pending: 'pending',
  }
  return map[status] || 'pending'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    success: '已完成',
    running: '解析中',
    failed: '失败',
    pending: '等待中',
  }
  return map[status] || status || '-'
}

async function loadBatches() {
  loading.value = true
  try {
    const res = await questionApi.importBatches()
    const data = res.data?.items || res.data?.results || res.data || []
    batches.value = Array.isArray(data) ? data : []
    // 自动轮询进行中的任务
    for (const b of batches.value) {
      const pid = b.paper
      const st = b.task_status || b.status
      if (pid && (st === 'running' || st === 'pending')) {
        startPolling(pid)
      }
    }
  } catch (e) {
    console.error('加载导入历史失败:', e)
  } finally {
    loading.value = false
  }
}

function startPolling(paperId: number) {
  if (pollingPapers.value.has(paperId)) return
  pollingPapers.value.add(paperId)

  const timer = setInterval(async () => {
    try {
      const res = await getParseProgress(paperId)
      if (res.code === 0 || res.success) {
        const batch = batches.value.find(b => b.paper === paperId)
        if (batch) {
          batch.progress = res.data?.progress ?? batch.progress
          batch.task_status = res.data?.task_status ?? batch.task_status
          batch.total_questions = res.data?.total_questions ?? batch.total_questions
        }
        if (['success', 'failed'].includes(res.data?.task_status)) {
          stopPolling(paperId)
          loadBatches()
        }
      }
    } catch (e) {
      // silent
    }
  }, 2000)

  pollingTimers.value.set(paperId, timer)
}

function stopPolling(paperId: number) {
  pollingPapers.value.delete(paperId)
  const timer = pollingTimers.value.get(paperId)
  if (timer) {
    clearInterval(timer)
    pollingTimers.value.delete(paperId)
  }
}

function clearAllPolling() {
  pollingTimers.value.forEach((timer) => clearInterval(timer))
  pollingTimers.value.clear()
  pollingPapers.value.clear()
}

function goReviewList(paperId: number) {
  if (paperId) {
    uni.navigateTo({ url: `/pages/teacher/review-list?paper_id=${paperId}` })
  }
}
</script>

<style scoped>
.import-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 240px;
  flex: 1;
  padding: 30rpx 40rpx;
}
.page-header {
  margin-bottom: 30rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.upload-area {
  border: 2rpx dashed #ddd;
  border-radius: 12rpx;
  padding: 80rpx 40rpx;
  text-align: center;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  margin-bottom: 30rpx;
}
.upload-area:hover {
  border-color: #409eff;
  background: #f5faff;
}
.upload-area.has-file {
  padding: 40rpx;
}
.upload-icon {
  font-size: 80rpx;
  display: block;
  margin-bottom: 20rpx;
}
.upload-text {
  color: #999;
  font-size: 28rpx;
}
.file-name {
  font-size: 28rpx;
  color: #409eff;
  font-weight: bold;
  display: block;
  margin-bottom: 20rpx;
}
.upload-btn {
  background: #409eff;
  color: #fff;
  font-size: 26rpx;
  padding: 16rpx 40rpx;
}
.uploading-text {
  color: #999;
  font-size: 26rpx;
}
.history-section {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.history-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 20rpx;
  display: block;
}
.history-list {
  max-height: 500px;
}
.batch-card {
  background: #f8f8f8;
  border-radius: 8rpx;
  padding: 16rpx;
  margin-bottom: 12rpx;
}
.batch-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 6rpx;
}
.batch-id {
  font-weight: bold;
  font-size: 24rpx;
  color: #999;
}
.batch-meta {
  display: flex;
  align-items: center;
  gap: 8rpx;
  flex: 1;
}
.batch-title {
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
}
.batch-count {
  font-size: 22rpx;
  color: #67c23a;
}
.batch-status {
  font-size: 22rpx;
  padding: 2rpx 12rpx;
  border-radius: 4rpx;
}
.batch-status.pending { color: #ff9800; background: #fff3e0; }
.batch-status.processing { color: #2196f3; background: #e3f2fd; }
.batch-status.completed { color: #4caf50; background: #e8f5e9; }
.batch-status.failed { color: #f44336; background: #ffebee; }
.batch-progress {
  font-size: 22rpx;
  color: #2196f3;
  font-weight: bold;
}
.batch-actions {
  display: flex;
  gap: 8rpx;
  margin-top: 8rpx;
}
.delete-btn {
  color: #e74c3c;
  border-color: #e74c3c;
  background: #fff;
}
.delete-btn:hover {
  background: #ffebee;
}
.loading {
  text-align: center;
  color: #999;
  padding: 40rpx;
  font-size: 24rpx;
}
.empty-history {
  text-align: center;
  padding: 60rpx;
  color: #999;
  font-size: 24rpx;
}
</style>
