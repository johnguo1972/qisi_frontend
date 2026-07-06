<template>
  <view class="class-requests">
    <TeacherSidebar activeItem="classes" />

    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <button class="btn-back" @click="goBack">返回</button>
        <text class="page-title">申请审批</text>
      </view>
      <!-- Tab 切换 -->
      <view class="tabs">
        <view
          v-for="tab in tabs"
          :key="tab.value"
          class="tab-item"
          :class="{ active: activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          <text>{{ tab.label }}</text>
          <text v-if="tab.count !== undefined && tab.count > 0" class="tab-badge">{{ tab.count }}</text>
        </view>
      </view>
      <!-- 列表内容 -->
      <view v-if="loading" class="loading">
        <text>加载中...</text>
      </view>
      <view v-else-if="filteredRequests.length === 0" class="empty">
        <text>暂无{{ tabLabel(activeTab) }}申请</text>
      </view>
      <view v-else class="request-list">
        <view v-for="req in filteredRequests" :key="req.id" class="request-card">
          <view class="card-info">
            <text class="req-name">{{ req.applicant_name || req.student_name }}</text>
            <text class="req-phone">{{ maskPhone(req.phone || req.mobile) }}</text>
            <text class="req-time">{{ formatTime(req.created_at) }}</text>
          </view>
          <view v-if="req.message" class="req-message">
            <text>{{ req.message }}</text>
          </view>
          <view v-if="req.status === 'pending'" class="card-actions">
            <button class="btn-reject" @click="handleReject(req.id)">拒绝</button>
            <button class="btn-approve" @click="handleApprove(req.id)">通过</button>
          </view>
          <view v-else class="card-status">
            <text :class="'status-' + req.status">{{ statusText(req.status) }}</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { classApi } from '@/api/index.ts'
import TeacherSidebar from '@/components/TeacherSidebar.vue'

interface JoinRequest {
  id: number
  applicant_name?: string
  student_name?: string
  phone?: string
  mobile?: string
  message?: string
  status: 'pending' | 'approved' | 'rejected'
  created_at?: string
}

interface TabDef {
  label: string
  value: 'all' | 'pending' | 'approved' | 'rejected'
  count?: number
}

const loading = ref(false)
const activeTab = ref<'all' | 'pending' | 'approved' | 'rejected'>('pending')
const allRequests = ref<JoinRequest[]>([])

let classId = 0

onMounted(async () => {
  // Get classId from route params
  const pages = getCurrentPages()
  const currentPage = pages[pages.length - 1]
  classId = Number(currentPage.options?.classId || 0)
  if (!classId) {
    uni.showToast({ title: '缺少班级ID', icon: 'none' })
    return
  }

  await loadRequests()
})

async function loadRequests() {
  loading.value = true
  try {
    const res = await classApi.joinRequests(classId)
    allRequests.value = res.data || []
  } catch (e) {
    console.error('Failed to load join requests:', e)
    uni.showToast({ title: '加载申请列表失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

const tabs = computed<TabDef[]>(() => {
  const counts = {
    pending: allRequests.value.filter(r => r.status === 'pending').length,
    approved: allRequests.value.filter(r => r.status === 'approved').length,
    rejected: allRequests.value.filter(r => r.status === 'rejected').length,
  }
  return [
    { label: '待审批', value: 'pending', count: counts.pending },
    { label: '已通过', value: 'approved', count: counts.approved },
    { label: '已拒绝', value: 'rejected', count: counts.rejected },
    { label: '全部', value: 'all' },
  ]
})

const filteredRequests = computed(() => {
  if (activeTab.value === 'all') return allRequests.value
  return allRequests.value.filter(r => r.status === activeTab.value)
})

function tabLabel(value: string): string {
  const map: Record<string, string> = {
    pending: '待审批',
    approved: '已通过',
    rejected: '已拒绝',
    all: '全部',
  }
  return map[value] || value
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    pending: '待审批',
    approved: '已通过',
    rejected: '已拒绝',
  }
  return map[status] || status
}

function maskPhone(phone?: string): string {
  if (!phone) return ''
  if (phone.length === 11) {
    return phone.substring(0, 3) + '****' + phone.substring(7)
  }
  return phone
}

function formatTime(dateStr?: string): string {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('zh-CN') + ' ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return dateStr
  }
}

async function handleApprove(requestId: number) {
  try {
    await classApi.approveRequest(requestId)
    uni.showToast({ title: '已通过', icon: 'success' })
    await loadRequests()
  } catch (e) {
    console.error('Failed to approve:', e)
    uni.showToast({ title: '操作失败', icon: 'error' })
  }
}

async function handleReject(requestId: number) {
  uni.showModal({
    title: '确认拒绝',
    content: '确定要拒绝该申请吗？',
    success: async (res) => {
      if (res.confirm) {
        try {
          await classApi.rejectRequest(requestId)
          uni.showToast({ title: '已拒绝', icon: 'success' })
          await loadRequests()
        } catch (e) {
          console.error('Failed to reject:', e)
          uni.showToast({ title: '操作失败', icon: 'error' })
        }
      }
    }
  })
}

function goBack() { uni.navigateBack() }
</script>

<style scoped>
.class-requests {
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
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 10rpx 0 30rpx;
}
.btn-back {
  background: #fff;
  color: #666;
  border: 1rpx solid #dcdfe6;
  border-radius: 8rpx;
  padding: 8rpx 20rpx;
  font-size: 24rpx;
  cursor: pointer;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.tabs {
  display: flex;
  gap: 16rpx;
  margin-bottom: 24rpx;
  border-bottom: 1rpx solid #e0e0e0;
  padding-bottom: 16rpx;
}
.tab-item {
  padding: 12rpx 24rpx;
  font-size: 26rpx;
  color: #666;
  cursor: pointer;
  border-radius: 8rpx;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.tab-item:hover {
  background: #f5f5f5;
}
.tab-item.active {
  background: #ecf5ff;
  color: #409eff;
  font-weight: bold;
}
.tab-badge {
  background: #e6a23c;
  color: #fff;
  font-size: 20rpx;
  padding: 2rpx 8rpx;
  border-radius: 50%;
  min-width: 28rpx;
  text-align: center;
}
.request-list {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}
.request-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.card-info {
  display: flex;
  align-items: center;
  gap: 20rpx;
  margin-bottom: 12rpx;
}
.req-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}
.req-phone {
  font-size: 24rpx;
  color: #999;
}
.req-time {
  font-size: 22rpx;
  color: #999;
  margin-left: auto;
}
.req-message {
  background: #f9f9f9;
  border-radius: 8rpx;
  padding: 12rpx 16rpx;
  margin-bottom: 12rpx;
}
.req-message text {
  font-size: 24rpx;
  color: #666;
}
.card-actions {
  display: flex;
  gap: 16rpx;
  justify-content: flex-end;
}
.btn-approve {
  background: #67c23a;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  padding: 12rpx 32rpx;
  font-size: 24rpx;
  cursor: pointer;
}
.btn-reject {
  background: #fff;
  color: #e74c3c;
  border: 1rpx solid #e74c3c;
  border-radius: 8rpx;
  padding: 12rpx 32rpx;
  font-size: 24rpx;
  cursor: pointer;
}
.card-status {
  text-align: right;
}
.status-approved {
  font-size: 24rpx;
  color: #67c23a;
}
.status-rejected {
  font-size: 24rpx;
  color: #e74c3c;
}
.loading, .empty {
  text-align: center;
  padding: 80rpx;
  color: #999;
  font-size: 26rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .main {
    margin-left: 60px;
    padding: 20rpx;
  }
  .card-info {
    flex-wrap: wrap;
    gap: 8rpx;
  }
  .req-time {
    margin-left: 0;
    width: 100%;
  }
}
</style>