<template>
  <view class="export-page">
    <!-- 顶部导航 -->
    <view class="nav-bar">
      <view class="nav-back" @click="goBack">
        <text class="back-icon">←</text>
        <text class="back-text">返回</text>
      </view>
      <text class="nav-title">导出 PDF</text>
      <view class="nav-placeholder"></view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading" class="center">
      <view class="spinner"></view>
      <text class="loading-text">正在加载导出信息...</text>
    </view>

    <!-- 导出表单 -->
    <view v-else class="form-container">
      <!-- 导出预览 -->
      <view class="preview-card">
        <text class="card-title">导出预览</text>
        <view class="preview-row">
          <text class="label">导出类型</text>
          <text class="value">{{ typeLabel }}</text>
        </view>
        <view class="preview-row">
          <text class="label">题目数量</text>
          <text class="value">{{ itemCount }} 道</text>
        </view>
      </view>

      <!-- 选项 -->
      <view class="option-card">
        <text class="card-title">导出选项</text>
        <view class="checkbox-row" @click="toggleAnswers">
          <view class="checkbox" :class="{ checked: includeAnswers }">
            <text v-if="includeAnswers" class="check-mark">✓</text>
          </view>
          <text class="checkbox-label">包含答案与解析</text>
        </view>
      </view>

      <!-- 水印设置 -->
      <view class="option-card">
        <text class="card-title">水印设置</text>
        <view class="input-row">
          <text class="input-label">水印文字</text>
          <input v-model="watermarkText" placeholder="留空则无水印" class="watermark-input" />
        </view>
      </view>

      <!-- 导出按钮 -->
      <button class="btn-export" :class="{ disabled: exporting }" @click="handleExport"
              :loading="exporting" :disabled="exporting">
        {{ exporting ? '正在导出...' : '开始导出' }}
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { exportApi } from '@/api/student.ts'

const loading = ref(true)
const exporting = ref(false)
const exportType = ref<'wrongbook' | 'mission'>('wrongbook')
const itemIds = ref<number[]>([])
const includeAnswers = ref(false)
const watermarkText = ref('')

const typeLabel = computed(() => exportType.value === 'wrongbook' ? '错题本' : '任务')
const itemCount = computed(() => itemIds.value.length)

onMounted(() => {
  try {
    const pages = getCurrentPages()
    const currentPage = pages[pages.length - 1] as any
    const options = currentPage.options || {}

    exportType.value = options.type === 'mission' ? 'mission' : 'wrongbook'

    if (options.ids) {
      itemIds.value = options.ids.split(',').map((s: string) => parseInt(s.trim(), 10)).filter((n: number) => !isNaN(n))
    }
  } catch (e) {
    console.error('解析路由参数失败:', e)
  } finally {
    loading.value = false
  }
})

function goBack() {
  uni.navigateBack()
}

function toggleAnswers() {
  includeAnswers.value = !includeAnswers.value
}

async function handleExport() {
  if (exporting.value || itemIds.value.length === 0) return

  exporting.value = true
  try {
    const res = await exportApi.exportPdf({
      export_type: exportType.value,
      item_ids: itemIds.value,
      include_answers: includeAnswers.value,
      watermark_text: watermarkText.value,
    })

    const downloadUrl = res.data?.download_url || res.data?.url
    if (downloadUrl) {
      uni.showToast({ title: '导出成功，正在下载...', icon: 'success' })
      // 优先使用浏览器下载，回退到 uni.openDocument
      // @ts-ignore
      if (typeof window !== 'undefined' && window.open) {
        window.open(downloadUrl, '_blank')
      } else {
        uni.downloadFile({
          url: downloadUrl,
          success: (downloadRes) => {
            uni.openDocument({
              filePath: downloadRes.tempFilePath,
              fileType: 'pdf',
              showMenu: true,
            })
          },
          fail: () => {
            uni.setClipboardData({
              data: downloadUrl,
              success: () => {
                uni.showToast({ title: '链接已复制，请浏览器打开', icon: 'none' })
              },
            })
          },
        })
      }
      // 延迟返回，让用户看到成功提示
      setTimeout(() => goBack(), 1500)
    } else {
      uni.showToast({ title: '导出成功，但未获取到下载链接', icon: 'none' })
    }
  } catch (e: any) {
    console.error('导出失败:', e)
    uni.showToast({ title: `导出失败: ${e.message || '请重试'}`, icon: 'none' })
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.export-page {
  min-height: 100vh;
  background: #f0f2f5;
}

/* 导航栏 */
.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 32rpx;
  background: #fff;
  border-bottom: 1rpx solid #e8e8e8;
}
.nav-back {
  display: flex;
  align-items: center;
  cursor: pointer;
}
.back-icon {
  font-size: 32rpx;
  color: #333;
  margin-right: 8rpx;
}
.back-text {
  font-size: 26rpx;
  color: #666;
}
.nav-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #333;
}
.nav-placeholder {
  width: 80rpx;
}

/* 居中加载 */
.center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120rpx 0;
}
.spinner {
  width: 60rpx;
  height: 60rpx;
  border: 6rpx solid #e8e8e8;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.loading-text {
  margin-top: 24rpx;
  color: #999;
  font-size: 26rpx;
}

/* 表单容器 */
.form-container {
  padding: 32rpx;
  display: flex;
  flex-direction: column;
  gap: 24rpx;
}

/* 卡片通用样式 */
.preview-card, .option-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 32rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.card-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 24rpx;
  padding-bottom: 16rpx;
  border-bottom: 1rpx solid #f0f0f0;
}

/* 预览行 */
.preview-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0;
}
.preview-row + .preview-row {
  border-top: 1rpx dashed #f0f0f0;
}
.label {
  font-size: 26rpx;
  color: #666;
}
.value {
  font-size: 28rpx;
  font-weight: 600;
  color: #333;
}

/* 复选框 */
.checkbox-row {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 8rpx 0;
}
.checkbox {
  width: 40rpx;
  height: 40rpx;
  border: 3rpx solid #ccc;
  border-radius: 8rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16rpx;
  transition: all 0.2s;
}
.checkbox.checked {
  background: #409eff;
  border-color: #409eff;
}
.check-mark {
  color: #fff;
  font-size: 24rpx;
  font-weight: bold;
}
.checkbox-label {
  font-size: 26rpx;
  color: #333;
}

/* 导出按钮 */
.btn-export {
  margin-top: 32rpx;
  padding: 24rpx;
  background: linear-gradient(135deg, #409eff, #2d8cf0);
  color: #fff;
  font-size: 30rpx;
  font-weight: bold;
  border: none;
  border-radius: 12rpx;
  line-height: 1.4;
}
.btn-export:active {
  opacity: 0.85;
}
.btn-export.disabled {
  background: #ccc;
  pointer-events: none;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .form-container {
    padding: 24rpx;
  }
}
</style>
