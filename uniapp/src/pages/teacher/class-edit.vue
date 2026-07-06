<template>
  <view class="edit-page">
    <TeacherSidebar activeItem="classes" />

    <!-- 右侧内容区 -->
    <view class="main">
      <view class="form">
        <view class="form-title">编辑班级</view>

        <!-- 邀请码信息区 -->
        <view class="invite-section">
          <view class="invite-header">
            <text class="invite-label">班级邀请码</text>
            <button size="mini" class="regen-btn" @click="handleRegenCode" :disabled="regenerating">
              {{ regenerating ? '生成中...' : '重新生成' }}
            </button>
          </view>
          <view class="invite-body">
            <text class="invite-code">{{ inviteCode || '暂无' }}</text>
            <button size="mini" class="copy-btn" @click="handleCopyCode" v-if="inviteCode">复制</button>
          </view>
          <text class="invite-hint">学生可通过此邀请码直接加入班级（需开启"允许邀请码加入"）</text>
        </view>

        <view class="form-item">
          <text class="label">班级名称 *</text>
          <input v-model="form.class_name" placeholder="请输入班级名称" />
        </view>

        <view class="form-item">
          <text class="label">班级描述</text>
          <textarea v-model="form.description" placeholder="可选" class="textarea" />
        </view>

        <view class="form-item">
          <text class="label">最大人数（0=不限制）</text>
          <input v-model.number="form.max_students" type="number" placeholder="0" />
        </view>

        <view class="form-item checkbox-row">
          <view class="checkbox" :class="{ checked: form.allow_invite_join }" @click="form.allow_invite_join = !form.allow_invite_join">
            <view class="checkmark"></view>
          </view>
          <text class="check-text">允许邀请码直接加入</text>
        </view>

        <view class="form-item">
          <text class="label">状态</text>
          <picker :range="statusOptions" @change="form.status = statusOptions[$event.detail.value]">
            <view class="picker-display">{{ statusTextMap[form.status] || '开放' }}</view>
          </picker>
        </view>

        <view class="btn-group">
          <button class="cancel-btn" @click="handleCancel">取消</button>
          <button class="submit-btn" @click="handleSubmit" :disabled="submitting">
            {{ submitting ? '保存中...' : '保存' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classApi } from '@/api/index.ts'
import TeacherSidebar from '@/components/TeacherSidebar.vue'

const statusOptions = ['open', 'closed', 'archived']
const statusTextMap: Record<string, string> = { open: '开放', closed: '已关闭', archived: '已归档' }

const classId = ref(0)
const inviteCode = ref('')
const regenerating = ref(false)
const form = ref({
  class_name: '',
  description: '',
  max_students: 0,
  allow_invite_join: true,
  status: 'open',
})
const submitting = ref(false)

// Use onLoad to get route parameters (works in H5 mode)
onLoad((options: any) => {
  classId.value = parseInt(options?.id || '0')

  if (!classId.value) {
    uni.showToast({ title: '缺少班级ID', icon: 'none' })
    return
  }

  loadClass()
})

async function loadClass() {
  try {
    const res = await classApi.detail(classId.value)
    if (res.data) {
      inviteCode.value = res.data.invite_code || ''
      form.value = {
        class_name: res.data.class_name || '',
        description: res.data.description || '',
        max_students: res.data.max_students || 0,
        allow_invite_join: res.data.allow_invite_join ?? true,
        status: res.data.status || 'open',
      }
    }
  } catch (e) {
    console.error('Failed to load class:', e)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

async function handleRegenCode() {
  uni.showModal({
    title: '重新生成邀请码',
    content: '原邀请码将立即失效，确定要重新生成吗？',
    success: async (res) => {
      if (!res.confirm) return
      regenerating.value = true
      try {
        const result: any = await classApi.regenerateCode(classId.value)
        if (result.code === 0 || result.data?.invite_code) {
          inviteCode.value = result.data?.invite_code || ''
          uni.showToast({ title: '新邀请码已生成', icon: 'success' })
        } else {
          uni.showToast({ title: result.message || '生成失败', icon: 'none' })
        }
      } catch (e: any) {
        console.error('Failed to regenerate code:', e)
        uni.showToast({ title: '生成失败', icon: 'none' })
      } finally {
        regenerating.value = false
      }
    }
  })
}

function handleCopyCode() {
  if (!inviteCode.value) return
  // #ifdef H5
  navigator.clipboard.writeText(inviteCode.value).then(() => {
    uni.showToast({ title: '已复制到剪贴板', icon: 'success' })
  }).catch(() => {
    uni.showToast({ title: '复制失败', icon: 'none' })
  })
  // #endif
}

function validate(): boolean {
  if (!form.value.class_name.trim()) {
    uni.showToast({ title: '请输入班级名称', icon: 'none' })
    return false
  }
  return true
}

async function handleSubmit() {
  if (!validate()) return
  if (!classId.value) {
    uni.showToast({ title: '班级ID无效', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const res: any = await classApi.update(classId.value, {
      class_name: form.value.class_name.trim(),
      description: form.value.description.trim(),
      max_students: form.value.max_students,
      allow_invite_join: form.value.allow_invite_join,
      status: form.value.status,
    })
    if (res.code === 0) {
      uni.showToast({ title: '保存成功', icon: 'success' })
      setTimeout(() => uni.navigateBack(), 1500)
    } else {
      uni.showToast({ title: res.message || '保存失败', icon: 'none' })
    }
  } catch (e: any) {
    console.error('Failed to update class:', e)
    uni.showToast({ title: '保存失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  uni.navigateBack()
}
</script>

<style scoped>
.edit-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 240px;
  flex: 1;
  padding: 30rpx 40rpx;
}
.form {
  background: #fff;
  border-radius: 12rpx;
  padding: 40rpx 32rpx;
}
.form-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 40rpx;
}

/* 邀请码区域 */
.invite-section {
  background: linear-gradient(135deg, #ecf5ff 0%, #f0f9ff 100%);
  border: 1rpx solid #b3d8ff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 40rpx;
}
.invite-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.invite-label {
  font-size: 26rpx;
  font-weight: bold;
  color: #409eff;
}
.regen-btn {
  background: #fff;
  color: #409eff;
  border: 1rpx solid #409eff;
  font-size: 22rpx;
  padding: 4rpx 16rpx;
  border-radius: 6rpx;
}
.regen-btn[disabled] {
  background: #f5f5f5;
  color: #ccc;
  border-color: #ddd;
}
.invite-body {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 12rpx;
}
.invite-code {
  font-size: 40rpx;
  font-weight: bold;
  color: #333;
  letter-spacing: 6rpx;
  font-family: 'Courier New', monospace;
}
.copy-btn {
  background: #409eff;
  color: #fff;
  border: none;
  font-size: 22rpx;
  padding: 4rpx 16rpx;
  border-radius: 6rpx;
}
.invite-hint {
  font-size: 22rpx;
  color: #909399;
  display: block;
}

.form-item {
  margin-bottom: 30rpx;
}
.label {
  font-size: 26rpx;
  color: #333;
  margin-bottom: 10rpx;
  display: block;
}
input {
  display: block;
  width: 100%;
  height: 56px;
  line-height: 28px;
  border: 2rpx solid #ddd;
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 26rpx;
  background: #fafafa;
  box-sizing: border-box;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}
input:focus {
  border-color: #409eff;
  background: #fff;
}
.textarea {
  width: 100%;
  min-height: 100rpx;
  border: 2rpx solid #ddd;
  border-radius: 8px;
  padding: 14px 16px;
  font-size: 26rpx;
  background: #fafafa;
  box-sizing: border-box;
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.checkbox {
  width: 32rpx;
  height: 32rpx;
  border: 2rpx solid #ddd;
  border-radius: 6rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.checkbox.checked {
  background: #409eff;
  border-color: #409eff;
}
.checkmark {
  width: 10rpx;
  height: 16rpx;
  border-left: 3rpx solid #fff;
  border-bottom: 3rpx solid #fff;
  transform: rotate(-45deg);
  opacity: 0;
}
.checkbox.checked .checkmark {
  opacity: 1;
}
.check-text {
  font-size: 24rpx;
  color: #666;
}
.picker-display {
  padding: 14px 16px;
  background: #fafafa;
  border: 2rpx solid #ddd;
  border-radius: 8px;
  font-size: 26rpx;
  color: #333;
}
.btn-group {
  display: flex;
  gap: 20rpx;
  margin-top: 50rpx;
}
.cancel-btn {
  flex: 1;
  background: #eee;
  color: #333;
  font-size: 28rpx;
  border-radius: 8rpx;
  border: none;
}
.submit-btn {
  flex: 2;
  background: #409eff;
  color: #fff;
  font-size: 28rpx;
  border-radius: 8rpx;
  border: none;
}
.submit-btn[disabled] {
  background: #a0cfff;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .main { margin-left: 60px; padding: 20rpx; }
  .form { max-width: 100%; }
}
</style>