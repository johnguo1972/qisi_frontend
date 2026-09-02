<template>
  <view class="sidebar">
    <view class="sidebar-logo">优途AI辅学系统</view>
    <view class="sidebar-user">
      <view class="user-info-row">
        <text class="user-name">{{ userName }}</text>
        <NicknameEditor :display-name="userName" @updated="handleProfileUpdated" />
      </view>
      <text class="user-role">家长</text>
      <RoleSwitcher />
    </view>
    <view class="nav-items">
      <view
        v-for="item in items"
        :key="item.key"
        class="nav-item"
        :class="{ active: activeItem === item.key }"
        @click="navigate(item.key)"
      >
        <text class="nav-icon">{{ item.icon }}</text>
        <text class="nav-text">{{ item.label }}</text>
      </view>
      <view class="nav-item nav-logout" @click="logout">
        <text class="nav-icon">🚪</text>
        <text class="nav-text">退出登录</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { authApi } from '@/api/index'
import { useUserStore } from '@/store/index'
import RoleSwitcher from '@/components/RoleSwitcher.vue'
import NicknameEditor from '@/components/NicknameEditor.vue'

defineProps<{ activeItem: string }>()
const emit = defineEmits<{ navigate: [key: string] }>()

const userStore = useUserStore()
const userName = computed(() => userStore.userInfo?.display_name || uni.getStorageSync('userInfo')?.display_name || '家长')
const items = [
  { key: 'home', label: '学习概览', icon: '📊' },
  { key: 'children', label: '孩子管理', icon: '👨‍👩‍👧' },
  { key: 'wrongbook', label: '错题分析', icon: '📝' },
  { key: 'practice', label: '精练题', icon: '📝' },
  { key: 'growth', label: '成长分析', icon: '📈' },
  { key: 'knowledge', label: '知识掌握', icon: '🧠' },
]

function navigate(key: string) {
  emit('navigate', key)
}

function handleProfileUpdated(profile: any) {
  userStore.setUserInfo(profile)
}

async function logout() {
  uni.showModal({
    title: '确认退出',
    content: '确定要退出登录吗？',
    success: async (result) => {
      if (!result.confirm) return
      try { await authApi.logout() } catch {}
      userStore.logout()
      uni.reLaunch({ url: '/pages/login/index' })
    },
  })
}
</script>

<style scoped>
.sidebar { width: 240px; background: #fff; box-shadow: 2px 0 8px rgba(0, 0, 0, .06); display: flex; flex-direction: column; position: fixed; left: 0; top: 0; bottom: 0; z-index: 10; }
.sidebar-logo { padding: 30rpx 24rpx; color: #409eff; font-size: 32rpx; font-weight: 700; border-bottom: 1rpx solid #f0f0f0; }
.sidebar-user { padding: 24rpx; border-bottom: 1rpx solid #f0f0f0; }
.user-info-row { display: flex; align-items: center; }
.user-name { flex: 1; min-width: 0; overflow: hidden; color: #333; font-size: 26rpx; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.user-role { display: block; margin-top: 6rpx; color: #999; font-size: 22rpx; }
.nav-items { flex: 1; padding: 16rpx 0; overflow-y: auto; }
.nav-item { display: flex; align-items: center; padding: 18rpx 24rpx; cursor: pointer; }
.nav-item:hover { background: #f5f5f5; }
.nav-item.active { background: #ecf5ff; }
.nav-icon { width: 38rpx; margin-right: 12rpx; font-size: 30rpx; text-align: center; }
.nav-text { color: #333; font-size: 26rpx; }
.nav-item.active .nav-text { color: #409eff; }
.nav-logout { margin-top: auto; }
.nav-logout .nav-text { color: #e74c3c; }
</style>
