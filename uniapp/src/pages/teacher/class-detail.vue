<template>
  <view class="class-detail">

    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <button class="btn-back" @click="goBack">返回</button>
        <text class="page-title">{{ classInfo.class_name || '班级详情' }}</text>
        <view class="page-actions">
          <button class="btn-edit" @click="goEdit">编辑</button>
          <button class="btn-delete" @click="confirmDelete">删除</button>
        </view>
      </view>
      <view v-if="loading" class="loading">
        <text>加载中...</text>
      </view>
      <template v-else-if="classInfo.id">
        <!-- 班级信息卡片 -->
        <view class="info-card">
          <view class="info-row">
            <text class="info-label">班级名称</text>
            <text class="info-value">{{ classInfo.class_name }}</text>
          </view>
          <view class="info-row">
            <text class="info-label">班级编号</text>
            <text class="info-value">{{ classInfo.class_no }}</text>
          </view>
          <view class="info-row">
            <text class="info-label">班级描述</text>
            <text class="info-value">{{ classInfo.description || '暂无描述' }}</text>
          </view>
          <view class="info-row">
            <text class="info-label">最大学生数</text>
            <text class="info-value">{{ classInfo.max_students || '不限制' }}</text>
          </view>
          <view class="info-row invite-row">
            <view class="invite-section">
              <text class="info-label">邀请码</text>
              <text class="invite-code">{{ classInfo.invite_code }}</text>
            </view>
            <button class="btn-refresh" size="mini" @click="handleRefreshCode">刷新邀请码</button>
          </view>
        </view>
        <!-- 操作按钮 -->
        <view class="action-bar">
          <button class="btn-requests" @click="goRequests">
            申请审批
            <text v-if="pendingCount > 0" class="badge">{{ pendingCount }}</text>
          </button>
        </view>
        <!-- 学生列表 -->
        <view class="student-section">
          <view class="section-header">
            <text class="section-title">学生列表 ({{ students.length }})</text>
          </view>
          <view v-if="students.length === 0" class="empty">
            <text>暂无学生加入</text>
          </view>
          <view v-else class="student-table">
            <view class="student-table-header">
              <text class="col-name">姓名</text>
              <text class="col-phone">手机号</text>
              <text class="col-join">加入方式</text>
            </view>
            <view v-for="s in students" :key="s.id" class="student-row">
              <text class="col-name">{{ s.display_name || s.student_name }}</text>
              <text class="col-phone">{{ maskPhone(s.phone || s.mobile) }}</text>
              <text class="col-join" :class="'badge-' + s.join_type">{{ joinTypeText(s.join_type) }}</text>
            </view>
          </view>
        </view>
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classApi } from '@/api/index.ts'

interface ClassInfo {
  id: number
  class_name: string
  class_no: string
  description?: string
  invite_code?: string
  max_students?: number
  status?: string
}

interface Student {
  id: number
  display_name?: string
  student_name?: string
  phone?: string
  mobile?: string
  join_type?: string
}

const loading = ref(false)
const classInfo = reactive<ClassInfo>({} as ClassInfo)
const students = ref<Student[]>([])

let classId = 0

// Use onLoad to get route parameters (works in H5 mode)
onLoad(async (options: any) => {
  classId = Number(options?.classId || 0)
  if (!classId) {
    uni.showToast({ title: '缺少班级ID', icon: 'none' })
    return
  }

  await loadClassDetail()
})

async function loadClassDetail() {
  loading.value = true
  try {
    const infoRes = await classApi.detail(classId)
    if (infoRes.data) {
      Object.assign(classInfo, infoRes.data)
    }
  } catch (e) {
    console.error('Failed to load class detail:', e)
    uni.showToast({ title: '加载班级信息失败', icon: 'none' })
  }

  try {
    const studentsRes = await classApi.students(classId)
    students.value = studentsRes.data?.items || []
  } catch (e) {
    console.error('Failed to load students:', e)
  } finally {
    loading.value = false
  }
}

const pendingCount = computed(() => {
  return students.value.filter(s => s.join_type === 'pending').length
})

function maskPhone(phone?: string): string {
  if (!phone) return ''
  if (phone.length === 11) {
    return phone.substring(0, 3) + '****' + phone.substring(7)
  }
  return phone
}

function joinTypeText(joinType?: string): string {
  const map: Record<string, string> = {
    direct: '直接加入',
    by_code: '邀请码',
    approved: '审核通过',
    pending: '待审核',
  }
  return map[joinType || ''] || joinType || '未知'
}

async function handleRefreshCode() {
  try {
    await classApi.regenerateCode(classId)
    // Reload to get new invite code
    const infoRes = await classApi.detail(classId)
    if (infoRes.data) {
      Object.assign(classInfo, infoRes.data)
    }
    uni.showToast({ title: '邀请码已刷新', icon: 'success' })
  } catch (e) {
    console.error('Failed to refresh code:', e)
    uni.showToast({ title: '刷新失败', icon: 'error' })
  }
}

function goBack() { uni.navigateBack() }
function goEdit() { uni.navigateTo({ url: `/pages/teacher/class-edit?id=${classId}` }) }
function goRequests() { uni.navigateTo({ url: `/pages/teacher/class-requests?classId=${classId}` }) }

async function confirmDelete() {
  uni.showModal({
    title: '确认删除',
    content: `确定要删除班级"${classInfo.class_name}"吗？\n\n删除前必须先移除所有学生和老师。`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await classApi.remove(classId)
          uni.showToast({ title: '删除成功', icon: 'success' })
          setTimeout(() => uni.navigateBack(), 1500)
        } catch (e: any) {
          const msg = e?.data?.message || '删除失败'
          uni.showToast({ title: msg, icon: 'none', duration: 3000 })
        }
      }
    }
  })
}
</script>

<style scoped>
.class-detail {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 0;
  flex: 1;
  padding: 30rpx 40rpx;
}
.page-header {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 10rpx 0 30rpx;
}
.page-actions {
  margin-left: auto;
  display: flex;
  gap: 12rpx;
}
.btn-edit {
  background: #ecf5ff;
  color: #409eff;
  border: none;
  border-radius: 6rpx;
  padding: 8rpx 20rpx;
  font-size: 22rpx;
}
.btn-delete {
  background: #fff0f0;
  color: #e74c3c;
  border: none;
  border-radius: 6rpx;
  padding: 8rpx 20rpx;
  font-size: 22rpx;
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
.info-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 32rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  margin-bottom: 20rpx;
}
.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
}
.info-row:last-child {
  border-bottom: none;
}
.info-label {
  font-size: 26rpx;
  color: #999;
  min-width: 160rpx;
}
.info-value {
  font-size: 26rpx;
  color: #333;
}
.invite-row {
  flex-wrap: nowrap;
}
.invite-section {
  display: flex;
  align-items: center;
  gap: 20rpx;
}
.invite-code {
  font-size: 28rpx;
  font-weight: bold;
  color: #409eff;
  letter-spacing: 4rpx;
}
.btn-refresh {
  background: #ecf5ff;
  color: #409eff;
  border: 1rpx solid #b3d8ff;
  border-radius: 6rpx;
  padding: 6rpx 16rpx;
  font-size: 22rpx;
  cursor: pointer;
}
.action-bar {
  margin-bottom: 20rpx;
}
.btn-requests {
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  padding: 16rpx 32rpx;
  font-size: 26rpx;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
}
.badge {
  background: #e74c3c;
  color: #fff;
  border-radius: 50%;
  padding: 2rpx 10rpx;
  font-size: 20rpx;
  min-width: 32rpx;
  text-align: center;
}
.student-section {
  background: #fff;
  border-radius: 12rpx;
  padding: 32rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.section-header {
  margin-bottom: 20rpx;
}
.section-title {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}
.empty {
  text-align: center;
  padding: 60rpx;
  color: #999;
  font-size: 26rpx;
}
.student-table-header {
  display: flex;
  padding: 12rpx 0;
  border-bottom: 2rpx solid #e0e0e0;
  font-weight: bold;
}
.student-row {
  display: flex;
  padding: 16rpx 0;
  border-bottom: 1rpx solid #f0f0f0;
  align-items: center;
}
.col-name {
  flex: 1;
  font-size: 26rpx;
  color: #333;
}
.col-phone {
  flex: 1;
  font-size: 24rpx;
  color: #666;
}
.col-join {
  flex: 1;
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 6rpx;
  text-align: center;
}
.badge-direct {
  background: #e8f5e9;
  color: #4caf50;
}
.badge-by_code {
  background: #e3f2fd;
  color: #2196f3;
}
.badge-approved {
  background: #e8f5e9;
  color: #4caf50;
}
.badge-pending {
  background: #fff3e0;
  color: #ff9800;
}
.loading {
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
  .info-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 8rpx;
  }
  .student-table-header, .student-row {
    font-size: 20rpx;
  }
}
</style>