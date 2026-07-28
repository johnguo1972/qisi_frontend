<template>
  <view class="modal-overlay" @click.self="$emit('close')">
    <view class="modal-content">
      <view class="modal-header">
        <text class="modal-title">导入题目</text>
        <text class="modal-close" @click="$emit('close')">&times;</text>
      </view>

      <view class="modal-body">
        <!-- 方式1: 拍照/图片 -->
        <view class="import-card" @click="$emit('photo-import')">
          <view class="import-icon-wrap">
            <text class="import-icon">&#128247;</text>
          </view>
          <view class="import-text">
            <text class="import-name">拍照/图片导入</text>
            <text class="import-desc">拍照或选择图片，AI自动识别题目</text>
          </view>
          <text class="import-arrow">&rsaquo;</text>
        </view>

        <!-- 方式2: PDF/Word -->
        <view class="import-card" @click="selectFile">
          <view class="import-icon-wrap">
            <text class="import-icon">&#128196;</text>
          </view>
          <view class="import-text">
            <text class="import-name">PDF/Word 导入</text>
            <text class="import-desc">上传 .docx / .pdf 文件，自动解析</text>
          </view>
          <text class="import-arrow">&rsaquo;</text>
        </view>

        <!-- 方式3: JSON数据包 -->
        <view class="import-card" @click="selectJson">
          <view class="import-icon-wrap">
            <text class="import-icon">&#128230;</text>
          </view>
          <view class="import-text">
            <text class="import-name">题库数据导入</text>
            <text class="import-desc">上传包含JSON和图片的ZIP压缩包</text>
          </view>
          <text class="import-arrow">&rsaquo;</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
// 修复Bug#1: 只保留一次defineEmits，放在最前面，确保emit变量可用
const emit = defineEmits(['close', 'photo-import', 'file-import', 'json-import'])

function selectFile() {
  // #ifdef H5
  uni.chooseFile({
    count: 1,
    extension: ['.docx', '.doc', '.pdf'],
    success: (res: any) => {
      const file = res.tempFiles?.[0]
      if (file) emit('file-import', file)
    },
    fail: (err: any) => {
      if (err?.errMsg && !err.errMsg.includes('cancel')) {
        console.error('选择文件失败:', err)
      }
    }
  })
  // #endif
  // #ifndef H5
  uni.showToast({ title: '请在H5端使用文件导入', icon: 'none' })
  // #endif
}

function selectJson() {
  // #ifdef H5
  uni.chooseFile({
    count: 1,
    extension: ['.zip'],
    success: (res: any) => {
      const file = res.tempFiles?.[0]
      if (file) emit('json-import', file)
    },
    fail: (err: any) => {
      if (err?.errMsg && !err.errMsg.includes('cancel')) {
        console.error('选择文件失败:', err)
      }
    }
  })
  // #endif
  // #ifndef H5
  uni.showToast({ title: '请在H5端使用JSON导入', icon: 'none' })
  // #endif
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #fff;
  border-radius: 12px;
  width: 480px;
  max-width: 90vw;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
}

.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.modal-close {
  font-size: 24px;
  color: #909399;
  cursor: pointer;
}

.modal-body {
  padding: 16px 20px;
}

.import-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.import-card:hover {
  border-color: #409eff;
  background: #fafcff;
}

.import-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: #f0f5ff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.import-icon {
  font-size: 24px;
}

.import-text {
  flex: 1;
}

.import-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  display: block;
  margin-bottom: 4px;
}

.import-desc {
  font-size: 12px;
  color: #909399;
  display: block;
}

.import-arrow {
  font-size: 20px;
  color: #c0c4cc;
}
</style>
