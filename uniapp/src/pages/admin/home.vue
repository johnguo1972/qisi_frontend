<template>
  <view class="admin-home">
    <!-- 左侧导航栏 -->
    <view class="sidebar">
      <view class="sidebar-logo">A自习室</view>
      <view class="sidebar-user">
        <text class="user-name">{{ userInfo.display_name }}</text>
        <text class="user-role">管理员</text>
      </view>
      <view class="nav-items">
        <view class="nav-item active">
          <text class="nav-icon">🏢</text>
          <text class="nav-text">机构管理</text>
        </view>
        <view class="nav-item nav-logout" @click="handleLogout">
          <text class="nav-icon">🚪</text>
          <text class="nav-text">退出登录</text>
        </view>
      </view>
    </view>
    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">机构管理</text>
        <button class="create-btn" @click="goCreate">+ 创建机构</button>
      </view>
      <view v-if="loading" class="loading">
        <text>加载中...</text>
      </view>
      <view v-else-if="items.length === 0" class="empty">
        <text>暂无机构，点击"创建机构"开始</text>
      </view>
      <view v-else class="inst-grid">
        <view v-for="inst in items" :key="inst.id" class="inst-card">
          <view class="card-main" @click="goDetail(inst.id)">
            <view class="card-header">
              <text class="inst-name">{{ inst.institution_name }}</text>
              <view class="status-tag" :class="inst.status">{{ statusText(inst.status) }}</view>
            </view>
            <view class="card-stats">
              <text class="stat">👨‍🏫 {{ inst.teacher_count }} 老师</text>
              <text class="stat">🏫 {{ inst.class_count }} 班级</text>
            </view>
          </view>
          <view class="card-actions">
            <button class="action-btn btn-edit" @click.stop="goEdit(inst.id)">编辑</button>
            <button class="action-btn btn-delete" @click.stop="confirmDelete(inst)">删除</button>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { institutionApi, authApi } from '@/api/index.ts'
import { useUserStore } from '@/store/index.ts'

const userInfo = ref({ display_name: '管理员' })
const items = ref<any[]>([])
const loading = ref(true)
const userStore = useUserStore()

async function loadInstitutions() {
  try {
    const res = await institutionApi.list()
    console.log('[admin] institutions loaded:', res)
    items.value = res.data?.items || []
  } catch (e: any) {
    console.error('[admin] Failed to load institutions:', e)
    uni.showToast({ title: `加载机构列表失败: ${e?.errMsg || '请重试'}`, icon: 'none', duration: 3000 })
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  console.log('[admin] home onMounted')
  try {
    const profile = await authApi.getProfile()
    if (profile.data) userInfo.value = profile.data
  } catch (e: any) {
    console.error('[admin] getProfile failed:', e)
  }

  await loadInstitutions()
})

let hasLoadedOnShow = false
onShow(async () => {
  if (hasLoadedOnShow) {
    await loadInstitutions()
  }
  hasLoadedOnShow = true
})

function statusText(status: string): string {
  const map: Record<string, string> = { active: '正常', suspended: '已停用', closed: '已关闭' }
  return map[status] || status
}

function goCreate() { uni.navigateTo({ url: '/pages/admin/institution-create' }) }
function goDetail(id: number) { uni.navigateTo({ url: `/pages/admin/institution-detail?id=${id}` }) }
function goEdit(id: number) { uni.navigateTo({ url: `/pages/admin/institution-edit?id=${id}` }) }

async function confirmDelete(inst: any) {
  uni.showModal({
    title: '确认删除',
    content: `确定要删除机构"${inst.institution_name}"吗？\n\n删除前必须先删除所有班级和老师。`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await institutionApi.remove(inst.id)
          uni.showToast({ title: '删除成功', icon: 'success' })
          await loadInstitutions()
        } catch (e: any) {
          const msg = e?.data?.message || '删除失败'
          uni.showToast({ title: msg, icon: 'none', duration: 3000 })
        }
      }
    }
  })
}

async function handleLogout() {
  uni.showModal({
    title: '确认退出',
    content: '确定要退出登录吗？',
    success: async (res) => {
      if (res.confirm) {
        try { await authApi.logout() } catch {}
        userStore.logout()
        uni.reLaunch({ url: '/pages/login/index' })
      }
    }
  })
}
</script>

<style scoped>
.admin-home {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.sidebar {
  width: 240px;
  background: #fff;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 10;
}
.sidebar-logo {
  padding: 30rpx 24rpx;
  font-size: 32rpx;
  font-weight: bold;
  color: #409eff;
  border-bottom: 1rpx solid #f0f0f0;
}
.sidebar-user {
  padding: 24rpx;
  border-bottom: 1rpx solid #f0f0f0;
}
.user-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
  display: block;
}
.user-role {
  font-size: 22rpx;
  color: #999;
  margin-top: 4rpx;
  display: block;
}
.nav-items {
  padding: 16rpx 0;
  flex: 1;
}
.nav-item {
  display: flex;
  align-items: center;
  padding: 16rpx 24rpx;
  cursor: pointer;
  transition: background 0.2s;
}
.nav-item:hover {
  background: #f5f5f5;
}
.nav-item.active {
  background: #ecf5ff;
  color: #409eff;
}
.nav-icon {
  font-size: 32rpx;
  margin-right: 12rpx;
}
.nav-text {
  font-size: 26rpx;
  color: #333;
}
.nav-logout:hover {
  background: #fff0f0;
}
.nav-logout .nav-icon {
  opacity: 0.7;
}
.nav-logout .nav-text {
  color: #e74c3c;
}
.main {
  margin-left: 240px;
  flex: 1;
  padding: 30rpx 40rpx;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.create-btn {
  background: #409eff;
  color: #fff;
  font-size: 24rpx;
  padding: 12rpx 24rpx;
  border-radius: 8rpx;
}
.inst-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20rpx;
}
.inst-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.card-actions {
  display: flex;
  gap: 12rpx;
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid #f0f0f0;
}
.action-btn {
  flex: 1;
  font-size: 22rpx;
  border-radius: 6rpx;
  border: none;
  padding: 8rpx;
}
.btn-edit {
  background: #ecf5ff;
  color: #409eff;
}
.btn-delete {
  background: #fff0f0;
  color: #e74c3c;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.inst-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}
.status-tag {
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 4rpx;
}
.status-tag.active { background: #e8f5e9; color: #4caf50; }
.status-tag.suspended { background: #fff3e0; color: #ff9800; }
.status-tag.closed { background: #f5f5f5; color: #999; }
.card-stats {
  display: flex;
  gap: 24rpx;
}
.stat {
  font-size: 22rpx;
  color: #666;
}
.loading, .empty {
  text-align: center;
  padding: 80rpx;
  color: #999;
  font-size: 26rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .sidebar {
    width: 60px;
  }
  .sidebar-user, .nav-text {
    display: none;
  }
  .sidebar-logo {
    font-size: 20rpx;
    text-align: center;
    padding: 20rpx 0;
  }
  .nav-item {
    justify-content: center;
    padding: 16rpx 0;
  }
  .nav-icon {
    margin-right: 0;
  }
  .main {
    margin-left: 60px;
    padding: 20rpx;
  }
  .inst-grid {
    grid-template-columns: 1fr;
  }
}
</style>
