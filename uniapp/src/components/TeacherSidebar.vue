<template>
  <view class="sidebar">
    <view class="sidebar-logo" @click="goWorkbench">A自习室</view>
    <view class="sidebar-user">
      <text class="user-name">{{ userInfo.display_name }}</text>
      <text class="user-role">教师</text>
    </view>
    <view class="nav-items">
      <view class="nav-item" :class="{ active: activeItem === 'workbench' }" @click="goWorkbench">
        <text class="nav-icon">&#128203;</text>
        <text class="nav-text">工作台</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'import' }" @click="goImport">
        <text class="nav-icon">&#128220;</text>
        <text class="nav-text">上传试卷</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'new-question' }" @click="goNewQuestion">
        <text class="nav-icon">&#10133;</text>
        <text class="nav-text">新增试题</text>
      </view>
      <view class="nav-group">
        <view class="nav-group-title">题库管理</view>
        <view class="nav-item" :class="{ active: activeItem === 'bank' }" @click="goBank">
          <text class="nav-icon">&#128218;</text>
          <text class="nav-text">题库列表</text>
        </view>
        <view class="nav-item" :class="{ active: activeItem === 'favorites' }" @click="goFavorites">
          <text class="nav-icon">&#11088;</text>
          <text class="nav-text">我的精选</text>
        </view>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'classes' }" @click="goClasses">
        <text class="nav-icon">&#127963;</text>
        <text class="nav-text">班级管理</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'missions' }" @click="goMissionList">
        <text class="nav-icon">&#128203;</text>
        <text class="nav-text">任务列表</text>
      </view>
      <view class="nav-item nav-logout" @click="handleLogout">
        <text class="nav-icon">&#128682;</text>
        <text class="nav-text">退出登录</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { authApi } from '@/api/index.ts'
import { useUserStore } from '@/store/index.ts'

const props = defineProps<{
  activeItem: string
}>()

const emit = defineEmits(['navigate'])

const userInfo = ref({ display_name: '老师' })
const userStore = useUserStore()

onMounted(async () => {
  try {
    const profile = await authApi.getProfile()
    if (profile.data) userInfo.value = profile.data
  } catch {}
})

function goWorkbench() { emit('navigate', 'workbench') }
function goImport() { emit('navigate', 'import') }
function goNewQuestion() { emit('navigate', 'new-question') }
function goBank() { emit('navigate', 'bank') }
function goFavorites() { emit('navigate', 'favorites') }
function goClasses() { emit('navigate', 'classes') }
function goMissionList() { emit('navigate', 'missions') }

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
    },
  })
}
</script>

<style scoped>
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
  cursor: pointer;
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
  overflow-y: auto;
}
.nav-group {
  margin-bottom: 8rpx;
}
.nav-group-title {
  padding: 8rpx 24rpx;
  font-size: 20rpx;
  color: #999;
  font-weight: bold;
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
.nav-item.active .nav-text {
  color: #409eff;
}
.nav-logout {
  margin-top: auto;
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
</style>