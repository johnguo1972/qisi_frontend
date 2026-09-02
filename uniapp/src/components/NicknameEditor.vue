<template>
  <view class="nickname-editor">
    <button class="edit-trigger" size="mini" @click="open">修改昵称</button>

    <view v-if="visible" class="dialog-overlay" @click="close">
      <view class="dialog" @click.stop>
        <view class="dialog-header">
          <text class="dialog-title">修改昵称</text>
          <text class="dialog-close" @click="close">×</text>
        </view>
        <view class="dialog-body">
          <input v-model="nickname" class="nickname-input" maxlength="64" placeholder="请输入昵称" />
        </view>
        <view class="dialog-footer">
          <button class="cancel-button" @click="close">取消</button>
          <button class="save-button" data-testid="save-nickname" :loading="saving" @click="save">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { authApi } from '@/api/index.ts'

const props = defineProps<{ displayName?: string }>()
const emit = defineEmits<{ updated: [profile: any] }>()

const visible = ref(false)
const nickname = ref('')
const saving = ref(false)

function open() {
  nickname.value = props.displayName || ''
  visible.value = true
}

function close() {
  if (!saving.value) visible.value = false
}

async function save() {
  const displayName = nickname.value.trim()
  if (!displayName) {
    uni.showToast({ title: '昵称不能为空', icon: 'none' })
    return
  }
  saving.value = true
  try {
    const response = await authApi.updateProfile({ display_name: displayName })
    if (response.code === 0 && response.data) {
      emit('updated', response.data)
      uni.showToast({ title: '昵称已更新', icon: 'success' })
      visible.value = false
      return
    }
    uni.showToast({ title: response.message || '昵称修改失败', icon: 'none' })
  } catch {
    uni.showToast({ title: '网络错误，请重试', icon: 'none' })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.nickname-editor { display: inline-flex; vertical-align: middle; }
.edit-trigger { min-width: auto; height: 42rpx; margin: 0 0 0 12rpx; padding: 0 12rpx; border: 1rpx solid #409eff; border-radius: 6rpx; color: #409eff; background: #fff; font-size: 20rpx; line-height: 40rpx; }
.dialog-overlay { position: fixed; inset: 0; z-index: 200; display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, .45); }
.dialog { width: 560rpx; overflow: hidden; border-radius: 14rpx; background: #fff; }
.dialog-header { display: flex; align-items: center; justify-content: space-between; padding: 28rpx 32rpx 20rpx; border-bottom: 1rpx solid #ebeef5; }
.dialog-title { color: #303133; font-size: 30rpx; font-weight: 700; }
.dialog-close { padding: 0 8rpx; color: #909399; font-size: 38rpx; line-height: 1; }
.dialog-body { padding: 30rpx 32rpx; }
.nickname-input { width: 100%; height: 72rpx; padding: 0 18rpx; border: 1rpx solid #dcdfe6; border-radius: 8rpx; color: #303133; font-size: 26rpx; box-sizing: border-box; }
.dialog-footer { display: flex; justify-content: flex-end; gap: 16rpx; padding: 0 32rpx 30rpx; }
.dialog-footer button { min-width: 126rpx; height: 64rpx; margin: 0; border-radius: 8rpx; font-size: 24rpx; line-height: 62rpx; }
.cancel-button { color: #606266; background: #fff; border: 1rpx solid #dcdfe6; }
.save-button { color: #fff; background: #409eff; border: 1rpx solid #409eff; }
</style>
