<template>
  <view v-if="embedded" class="embedded-content"><slot /></view>
  <view v-else class="layout">
    <!-- H5/APP 与学生端、教师端保持固定左侧导航。 -->
    <!-- #ifndef MP-WEIXIN -->
    <ParentSidebar :active-item="activeItem" @navigate="navigate" />
    <view class="content-area"><slot /></view>
    <!-- #endif -->

    <!-- 微信小程序使用独立的全宽布局和菜单抽屉，不参与桌面 flex 排版。 -->
    <!-- #ifdef MP-WEIXIN -->
    <view class="mp-layout">
      <view class="mp-header">
        <button class="menu-button" @click="drawerVisible = true">☰ 菜单</button>
        <text class="mp-title">家长端</text>
      </view>
      <view class="mp-content"><slot /></view>
    </view>
    <MpDrawer
      :visible="drawerVisible"
      :items="drawerItems"
      :user-name="userName"
      role-label="家长"
      @close="drawerVisible = false"
      @navigate="navigate"
      @logout="logout"
    />
    <!-- #endif -->
  </view>
</template>

<script setup lang="ts">
import { computed, inject, provide, ref } from 'vue'
import { authApi } from '@/api/index'
import { useUserStore } from '@/store/index'
import ParentSidebar from '@/components/ParentSidebar.vue'
import MpDrawer from '@/components/MpDrawer.vue'
import { navigateRoleSection } from '@/utils/role-navigation'

const props = withDefaults(defineProps<{ activeItem: string; inline?: boolean }>(), { inline: false })
const emit = defineEmits<{ sectionChange: [key: string] }>()
const drawerVisible = ref(false)
const userStore = useUserStore()
const inheritedEmbedded = inject('parentLayoutEmbedded', false)
const inheritedNavigate = inject<(key: string) => void>('parentLayoutNavigate', undefined)
const embedded = Boolean(inheritedEmbedded)
const userName = computed(() => userStore.userInfo?.display_name || uni.getStorageSync('userInfo')?.display_name || '家长')
const drawerItems = [
  { key: 'home', icon: '📊', label: '学习概览' },
  { key: 'children', icon: '👨‍👩‍👧', label: '孩子管理' },
  { key: 'wrongbook', icon: '📝', label: '错题分析' },
  { key: 'practice', icon: '📝', label: '精练题' },
  { key: 'growth', icon: '📈', label: '成长分析' },
  { key: 'knowledge', icon: '🧠', label: '知识掌握' },
]

function navigate(key: string) {
  drawerVisible.value = false
  if (props.inline && key === props.activeItem) return
  if (props.inline) {
    emit('sectionChange', key)
    return
  }
  const routes: Record<string, string> = {
    home: '/pages/parent/home',
    children: '/pages/parent/bind',
    wrongbook: '/pages/parent/wrongbook',
    practice: '/pages/parent/practice',
    growth: '/pages/parent/growth',
    knowledge: '/pages/parent/knowledge',
  }
  // #ifndef MP-WEIXIN
  navigateRoleSection('parent', key)
  // #endif
  // #ifdef MP-WEIXIN
  if (!routes[key]) return
  uni.navigateTo({ url: routes[key] })
  // #endif
}

provide('parentLayoutEmbedded', props.inline || embedded)
provide('parentLayoutNavigate', props.inline || !inheritedNavigate ? navigate : inheritedNavigate)

async function logout() {
  drawerVisible.value = false
  try { await authApi.logout() } catch {}
  userStore.logout()
  uni.reLaunch({ url: '/pages/login/index' })
}
</script>

<style scoped>
.layout { display: flex; width: 100%; min-width: 0; min-height: 100vh; box-sizing: border-box; background: #f0f2f5; }
.embedded-content { width: 100%; }
.content-area { flex: 1; min-width: 0; margin-left: 240px; padding: 30rpx 40rpx; box-sizing: border-box; }
.mp-layout { width: 100%; min-height: 100vh; background: #f0f2f5; box-sizing: border-box; }
.mp-header { display: flex; align-items: center; gap: 18rpx; width: 100%; min-height: 84rpx; padding: 12rpx 20rpx; background: #f8f8f8; box-sizing: border-box; }
.menu-button { flex: 0 0 auto; height: 64rpx; margin: 0; padding: 0 22rpx; color: #409eff; background: #fff; border: 1rpx solid #e5e7eb; border-radius: 12rpx; font-size: 24rpx; line-height: 64rpx; }
.mp-title { flex: 1; overflow: hidden; color: #303133; font-size: 30rpx; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.mp-content { width: 100%; padding: 0 20rpx 40rpx; box-sizing: border-box; }
.mp-content :deep(.page) { width: 100%; min-height: calc(100vh - 108rpx); padding: 18rpx 0 60rpx; box-sizing: border-box; }
.mp-content :deep(.switcher) { margin-left: 0; margin-right: 0; }
.mp-content :deep(.state-card), .mp-content :deep(.card), .mp-content :deep(.list), .mp-content :deep(.stats) { width: 100%; box-sizing: border-box; }
@media (max-width: 768px) {
  .content-area { padding: 16rpx 20rpx; }
}
</style>
