<template>
  <view class="edit-page">
    <view class="form">
      <view class="form-title">编辑机构</view>

      <view class="form-item">
        <text class="label">机构名称 *</text>
        <input v-model="form.institution_name" placeholder="请输入机构名称" />
      </view>

      <view class="form-item">
        <text class="label">联系人 *</text>
        <input v-model="form.contact_name" placeholder="请输入联系人姓名" />
      </view>

      <view class="form-item">
        <text class="label">联系电话 *</text>
        <input v-model="form.contact_phone" type="number" placeholder="请输入联系电话" />
      </view>

      <view class="form-item">
        <text class="label">联系邮箱</text>
        <input v-model="form.contact_email" placeholder="请输入联系邮箱（选填）" />
      </view>

      <view class="form-item">
        <text class="label">机构地址</text>
        <input v-model="form.address" placeholder="请输入机构地址（选填）" />
      </view>

      <view class="form-item">
        <text class="label">状态</text>
        <picker :range="statusOptions" @change="form.status = statusOptions[$event.detail.value]">
          <view class="picker-display">{{ statusOptions.includes(form.status) ? form.status : 'active' }}</view>
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
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { institutionApi } from '@/api/institutions.ts'

const statusOptions = ['active', 'suspended', 'closed']
const statusLabels: Record<string, string> = { active: '正常', suspended: '已暂停', closed: '已关闭' }

const institutionId = ref(0)
const form = ref({
  institution_name: '',
  contact_name: '',
  contact_phone: '',
  contact_email: '',
  address: '',
  status: 'active',
})
const submitting = ref(false)

onLoad((options: any) => {
  institutionId.value = parseInt(options?.id || '0')
})

onMounted(async () => {
  if (!institutionId.value) {
    uni.showToast({ title: '缺少机构ID', icon: 'none' })
    return
  }

  try {
    const res = await institutionApi.detail(institutionId.value)
    if (res.data) {
      form.value = {
        institution_name: res.data.institution_name || '',
        contact_name: res.data.contact_name || '',
        contact_phone: res.data.contact_phone || '',
        contact_email: res.data.contact_email || '',
        address: res.data.address || '',
        status: res.data.status || 'active',
      }
    }
  } catch (e) {
    console.error('Failed to load institution:', e)
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
})

function validate(): boolean {
  if (!form.value.institution_name.trim()) {
    uni.showToast({ title: '请输入机构名称', icon: 'none' })
    return false
  }
  if (!form.value.contact_name.trim()) {
    uni.showToast({ title: '请输入联系人姓名', icon: 'none' })
    return false
  }
  if (!form.value.contact_phone.trim()) {
    uni.showToast({ title: '请输入联系电话', icon: 'none' })
    return false
  }
  return true
}

async function handleSubmit() {
  if (!validate()) return
  submitting.value = true
  try {
    await institutionApi.update(institutionId.value, {
      institution_name: form.value.institution_name.trim(),
      contact_name: form.value.contact_name.trim(),
      contact_phone: form.value.contact_phone.trim(),
      contact_email: form.value.contact_email.trim(),
      address: form.value.address.trim(),
      status: form.value.status,
    })
    uni.showToast({ title: '保存成功', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 1500)
  } catch (e) {
    console.error('Failed to update institution:', e)
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
  min-height: 100vh;
  background: #f0f2f5;
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
</style>
