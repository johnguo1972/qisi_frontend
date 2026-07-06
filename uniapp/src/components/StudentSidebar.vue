<template>
  <view class="sidebar">
    <view class="sidebar-logo" @click="goHome">A自习室</view>
    <view class="sidebar-user">
      <text class="user-name">{{ userInfo.display_name || '同学' }}</text>
      <text class="user-role">学生</text>
    </view>
    <view class="nav-items">
      <view class="nav-item" :class="{ active: activeItem === 'home' }" @click="goHome">
        <text class="nav-icon">&#128203;</text>
        <text class="nav-text">首页</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'wrongbook' }" @click="goWrongBook">
        <text class="nav-icon">&#10060;</text>
        <text class="nav-text">错题本</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'knowledge' }" @click="goKnowledgeGraph">
        <text class="nav-icon">&#127757;</text>
        <text class="nav-text">知识图谱</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'growth' }" @click="goGrowth">
        <text class="nav-icon">&#128200;</text>
        <text class="nav-text">成长</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'join-class' }" @click="goJoinClass">
        <text class="nav-icon">&#128101;</text>
        <text class="nav-text">加入班级</text>
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

const userInfo = ref({ display_name: '同学' })
const userStore = useUserStore()

onMounted(async () => {
  try {
    const profile = await authApi.getProfile()
    if (profile.data) userInfo.value = profile.data
  } catch {}
})

function goHome() { uni.navigateTo({ url: '/pages/student/home' }) }
function goWrongBook() { uni.navigateTo({ url: '/pages/student/wrongbook' }) }
function goKnowledgeGraph() { uni.navigateTo({ url: '/pages/student/knowledge-graph' }) }
function goGrowth() { uni.navigateTo({ url: '/pages/student/growth' }) }
function goJoinClass() { uni.navigateTo({ url: '/pages/student/join-class' }) }

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
