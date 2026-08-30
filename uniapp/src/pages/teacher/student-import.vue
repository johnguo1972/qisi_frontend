<template>
  <view class="page">
    <view class="card">
      <text class="title">批量导入学生</text>
      <text class="hint">模板列：姓名（必填）、手机号、学号、班级标识、年级。支持 CSV / XLSX，单次最多 5000 行。</text>
      <button size="mini" @click="downloadTemplate">下载导入模板</button>
      <!-- #ifdef H5 -->
      <input type="file" accept=".csv,.xlsx" @change="selectFile" />
      <!-- #endif -->
      <!-- #ifndef H5 -->
      <button type="primary" @click="chooseFile">选择文件</button>
      <!-- #endif -->
      <text v-if="fileName" class="file-name">{{ fileName }}</text>
      <button type="primary" :disabled="!file || loading" @click="submit">{{ loading ? '导入中...' : '开始导入' }}</button>
    </view>
    <view v-if="result" class="card result">
      <text class="title">导入结果</text>
      <text>状态：{{ result.status }}</text>
      <text>总行数：{{ result.total_count }}　成功：{{ result.success_count }}　失败：{{ result.failed_count }}</text>
      <button v-if="result.failed_count" size="mini" @click="showErrors">查看错误行</button>
      <button v-if="result.failed_count" size="mini" @click="downloadErrors">下载错误明细</button>
      <view v-if="errors.length" class="errors">
        <text v-for="item in errors" :key="item.row_no">第{{ item.row_no }}行：{{ item.error_message }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classApi } from '@/api/institutions'
import { apiBaseUrl } from '@/utils/api-config'

const classId = ref('')
const file = ref<File | null>(null)
const fileName = ref('')
const loading = ref(false)
const result = ref<any>(null)
const errors = ref<any[]>([])

onLoad((options: any) => { classId.value = String(options?.classId || '') })

function selectFile(event: any) {
  file.value = event?.target?.files?.[0] || null
  fileName.value = file.value?.name || ''
}

function chooseFile() {
  uni.showToast({ title: '请在 H5 端选择 CSV/XLSX 文件', icon: 'none' })
}

async function submit() {
  if (!classId.value || !file.value) return
  loading.value = true
  try {
    const response: any = await classApi.importStudents(classId.value, file.value)
    result.value = response.data || null
    if (result.value?.id && result.value.status === 'validating') {
      result.value = await waitForImport(result.value.id)
    }
    if (result.value?.failed_count) await showErrors()
    uni.showToast({ title: '导入完成', icon: 'success' })
  } catch (error: any) {
    uni.showToast({ title: error?.message || '导入失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function waitForImport(taskId: string): Promise<any> {
  const terminal = new Set(['succeeded', 'partially_succeeded', 'failed'])
  const deadline = Date.now() + 120000
  let latest = result.value
  while (Date.now() < deadline && !terminal.has(latest?.status)) {
    await new Promise(resolve => setTimeout(resolve, 500))
    const response = await fetch(`${apiBaseUrl}/student-imports/${taskId}`, {
      headers: { Authorization: `Bearer ${uni.getStorageSync('accessToken')}` },
    })
    if (!response.ok) throw new Error('查询导入进度失败')
    const data = await response.json()
    latest = data.data || latest
  }
  if (!terminal.has(latest?.status)) throw new Error('导入任务处理超时，请稍后查看任务状态')
  return latest
}

async function showErrors() {
  if (!result.value?.id) return
  const response = await fetch(`${apiBaseUrl}/student-imports/${result.value.id}/errors`, {
    headers: { Authorization: `Bearer ${uni.getStorageSync('accessToken')}` },
  })
  const data = await response.json()
  errors.value = data.data?.items || []
}

async function downloadErrors() {
  if (!result.value?.id) return
  try {
    const response = await fetch(`${apiBaseUrl}/student-imports/${result.value.id}/errors`, {
      headers: { Authorization: `Bearer ${uni.getStorageSync('accessToken')}` },
    })
    const data = await response.json()
    const downloadUrl = data.data?.download_url
    if (!downloadUrl) throw new Error('暂无错误明细')
    const fileResponse = await fetch(downloadUrl, {
      headers: { Authorization: `Bearer ${uni.getStorageSync('accessToken')}` },
    })
    if (!fileResponse.ok) throw new Error('错误明细下载失败')
    const url = URL.createObjectURL(await fileResponse.blob())
    const link = document.createElement('a')
    link.href = url
    link.download = 'student-import-errors.csv'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    uni.showToast({ title: error?.message || '错误明细下载失败', icon: 'none' })
  }
}

async function downloadTemplate() {
  if (!classId.value) return
  try {
    const response = await fetch(`${apiBaseUrl}/classes/${classId.value}/students/import-template`, {
      headers: { Authorization: `Bearer ${uni.getStorageSync('accessToken')}` },
    })
    if (!response.ok) throw new Error('模板下载失败')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'student-import-template.csv'
    link.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    uni.showToast({ title: error?.message || '模板下载失败', icon: 'none' })
  }
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 32rpx; background: #f4f6f8; }
.card { display: flex; flex-direction: column; gap: 20rpx; max-width: 900px; margin: 0 auto 24rpx; padding: 32rpx; background: #fff; border-radius: 12rpx; }
.title { font-size: 34rpx; font-weight: bold; color: #303133; }
.hint, .file-name { color: #606266; font-size: 26rpx; line-height: 1.6; }
.result text { display: block; }
.errors { display: flex; flex-direction: column; gap: 8rpx; color: #f56c6c; font-size: 24rpx; }
</style>
