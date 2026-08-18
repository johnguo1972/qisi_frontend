<template>
  <ParentShell active-item="children">
  <view class="page">
    <view class="card">
      <text class="title">添加孩子</text>
      <text class="hint">请向学生获取申请码。提交后，需要学生在学生端确认，确认前不会开放孩子的学习数据。</text>
      <input v-model="bindCode" class="input" maxlength="8" placeholder="请输入8位申请码" />
      <picker :range="relationLabels" @change="onRelationChange">
        <view class="picker">关系：{{ relationLabels[relationIndex] }} ▼</view>
      </picker>
      <button class="primary" :loading="submitting" @click="submit">提交绑定申请</button>
    </view>

    <view class="card">
      <view class="section-title">已绑定孩子</view>
      <view v-if="!children.length" class="empty">暂无已确认的孩子</view>
      <view v-for="item in children" :key="item.id" class="child-row">
        <view><text class="student-name">{{ item.display_name || '学生' }}</text><text class="student-status">{{ item.grade_level || '年级未设置' }}</text></view>
        <button class="remove" :disabled="removing === item.id" @click="remove(item)">解除绑定</button>
      </view>
    </view>

    <view class="card">
      <view class="section-title">待确认申请</view>
      <view v-if="!requests.length" class="empty">暂无待确认申请</view>
      <view v-for="item in requests" :key="item.id" class="request-row">
        <view>
          <text class="student-name">{{ item.student_name || '学生' }}</text>
          <text class="student-status">等待学生确认 · {{ relationLabel(item.relation_type) }}</text>
        </view>
      </view>
    </view>
  </view>
  </ParentShell>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { parentApi } from '@/api/index'
import ParentShell from '@/components/ParentShell.vue'
import { ensurePageRole } from '@/utils/roles'

const bindCode = ref('')
const relationIndex = ref(2)
const relationValues = ['father', 'mother', 'guardian']
const relationLabels = ['父亲', '母亲', '监护人']
const requests = ref<any[]>([])
const children = ref<any[]>([])
const submitting = ref(false)
const removing = ref('')

function relationLabel(value: string) {
  return ({ father: '父亲', mother: '母亲', guardian: '监护人' } as Record<string, string>)[value] || '监护人'
}

function onRelationChange(event: any) {
  relationIndex.value = Number(event?.detail?.value || 0)
}

function responseMessage(response: any, fallback: string) {
  return response?.detail || response?.message || fallback
}

async function submit() {
  const code = bindCode.value.trim().toUpperCase()
  if (!/^[A-Z0-9]{8}$/.test(code)) {
    uni.showToast({ title: '请输入正确的8位申请码', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const response: any = await parentApi.createBindRequest(code, relationValues[relationIndex.value])
    if (response?.code !== 0) throw new Error(responseMessage(response, '绑定申请提交失败'))
    bindCode.value = ''
    uni.showToast({ title: '申请已提交，等待学生确认', icon: 'none' })
    await loadData()
  } catch (error: any) {
    uni.showToast({ title: error?.message || '绑定申请提交失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

async function loadData() {
  try {
    const [pendingResponse, childrenResponse]: any[] = await Promise.all([
      parentApi.pendingRequests(),
      parentApi.children(),
    ])
    if (pendingResponse?.code !== 0) throw new Error(responseMessage(pendingResponse, '申请列表加载失败'))
    if (childrenResponse?.code !== 0) throw new Error(responseMessage(childrenResponse, '孩子列表加载失败'))
    requests.value = Array.isArray(pendingResponse.data) ? pendingResponse.data : []
    children.value = Array.isArray(childrenResponse.data) ? childrenResponse.data : []
  } catch (error: any) {
    uni.showToast({ title: error?.message || '申请列表加载失败', icon: 'none' })
  }
}

async function remove(item: any) {
  const confirmed = await new Promise<boolean>(resolve => {
    uni.showModal({ title: '解除绑定', content: `确定解除与${item.display_name || '该学生'}的绑定吗？`, success: result => resolve(!!result.confirm) })
  })
  if (!confirmed) return
  removing.value = item.id
  try {
    const response: any = await parentApi.removeBind(String(item.id))
    if (response?.code !== 0) throw new Error(responseMessage(response, '解除绑定失败'))
    uni.showToast({ title: '绑定已解除', icon: 'success' })
    await loadData()
  } catch (error: any) {
    uni.showToast({ title: error?.message || '解除绑定失败', icon: 'none' })
  } finally {
    removing.value = ''
  }
}

onMounted(() => {
  if (!ensurePageRole('parent')) return
  loadData()
})
</script>

<style scoped>
.page { min-height: 100vh; padding: 30rpx 24rpx 60rpx; box-sizing: border-box; background: #f0f2f5; }
.card { margin-bottom: 24rpx; padding: 32rpx; border-radius: 18rpx; background: #fff; }
.title { display: block; color: #303133; font-size: 36rpx; font-weight: 700; }
.hint { display: block; margin-top: 18rpx; color: #909399; font-size: 24rpx; line-height: 1.6; }
.input, .picker { height: 82rpx; margin-top: 24rpx; padding: 0 18rpx; box-sizing: border-box; border: 1rpx solid #dcdfe6; border-radius: 10rpx; color: #303133; line-height: 82rpx; font-size: 26rpx; }
.picker { margin-top: 16rpx; color: #606266; }
.primary { margin-top: 26rpx; color: #fff; background: #409eff; font-size: 26rpx; }
.section-title { display: block; margin-bottom: 18rpx; color: #303133; font-size: 29rpx; font-weight: 600; }
.empty { padding: 44rpx 0; color: #909399; text-align: center; font-size: 24rpx; }
.request-row { padding: 20rpx 0; border-top: 1rpx solid #f0f0f0; }
.child-row { display: flex; align-items: center; justify-content: space-between; gap: 16rpx; padding: 20rpx 0; border-top: 1rpx solid #f0f0f0; }
.student-name, .student-status { display: block; }
.student-name { color: #303133; font-size: 27rpx; }
.student-status { margin-top: 8rpx; color: #e6a23c; font-size: 23rpx; }
.remove { margin: 0; padding: 0 16rpx; color: #f56c6c; background: #fff; border: 1rpx solid #fbc4c4; font-size: 22rpx; line-height: 2.2; }
</style>
