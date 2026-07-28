<template>
  <view class="modal-overlay" @click.self="$emit('close')">
    <view class="modal-content">
      <view class="modal-header">
        <text class="modal-title">新增题目</text>
        <text class="modal-close" @click="$emit('close')">&times;</text>
      </view>
      <view class="modal-body">
        <view class="menu-item" @click="$emit('photo')">
          <text class="menu-icon">&#128247;</text>
          <view class="menu-info">
            <text class="menu-name">拍照识别</text>
            <text class="menu-desc">拍照或选图，AI自动识别</text>
          </view>
        </view>
        <view class="menu-item" @click="$emit('file')">
          <text class="menu-icon">&#128196;</text>
          <view class="menu-info">
            <text class="menu-name">PDF/Word导入</text>
            <text class="menu-desc">上传文档自动解析</text>
          </view>
        </view>
        <view class="menu-item" @click="$emit('json')">
          <text class="menu-icon">&#128230;</text>
          <view class="menu-info">
            <text class="menu-name">JSON数据包导入</text>
            <text class="menu-desc">上传ZIP压缩包批量导入</text>
          </view>
        </view>
        <view class="menu-item" @click="$emit('manual')">
          <text class="menu-icon">&#9998;&#65039;</text>
          <view class="menu-info">
            <text class="menu-name">手动创建</text>
            <text class="menu-desc">手动填写题目信息</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
defineEmits(['close', 'photo', 'file', 'json', 'manual'])
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: #fff; border-radius: 12px;
  width: 400px; max-width: 90vw; overflow: hidden;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #f0f0f0;
}
.modal-title { font-size: 16px; font-weight: 600; color: #303133; }
.modal-close { font-size: 24px; color: #909399; cursor: pointer; }
.modal-body { padding: 8px 0; }
.menu-item {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 20px; cursor: pointer;
}
.menu-item:hover { background: #f5f7fa; }
.menu-icon { font-size: 24px; width: 36px; text-align: center; }
.menu-info { flex: 1; }
.menu-name { font-size: 14px; font-weight: 500; color: #303133; display: block; }
.menu-desc { font-size: 12px; color: #909399; display: block; margin-top: 2px; }
</style>
