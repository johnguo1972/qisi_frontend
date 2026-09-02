<template>
  <view v-if="visible" class="layer" @click="$emit('close')">
      <view class="drawer" @click.stop>
        <view class="profile">
        <view class="profile-name-row">
          <text>👤 {{ userName }}</text>
          <NicknameEditor :display-name="userName" @updated="handleProfileUpdated" />
        </view>
        <text>{{ roleLabel }}</text>
        <!-- #ifdef MP-WEIXIN -->
        <MpRoleSwitcher />
        <!-- #endif -->
        <!-- #ifndef MP-WEIXIN -->
        <RoleSwitcher />
        <!-- #endif -->
      </view>
      <view v-for="item in props.items" :key="item.key" class="item" @click="$emit('navigate', item.key)">
        {{ item.icon }} {{ item.label }}
      </view>
      <view class="logout" @click="$emit('logout')">🚪 退出登录</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import RoleSwitcher from '@/components/RoleSwitcher.vue'
import NicknameEditor from '@/components/NicknameEditor.vue'
import { useUserStore } from '@/store/index'
// #ifdef MP-WEIXIN
import MpRoleSwitcher from '@/components/MpRoleSwitcher.vue'
// #endif

type DrawerItem = { key: string; icon: string; label: string }

const props = withDefaults(defineProps<{
  visible: boolean
  userName?: string
  roleLabel?: string
  items?: DrawerItem[]
}>(), {
  items: () => [
    { key: 'home', icon: '📋', label: '首页' },
    { key: 'wrongbook', icon: '❌', label: '错题本' },
    { key: 'practice', icon: '📝', label: '精练题' },
    { key: 'knowledge', icon: '🗺', label: '知识图谱' },
    { key: 'growth', icon: '📈', label: '成长' },
    { key: 'join-class', icon: '👥', label: '加入班级' },
    { key: 'parent-bind', icon: '👨‍👩‍👧', label: '家长绑定' },
  ],
})

defineEmits<{ close: []; navigate: [key: string]; logout: [] }>()

const userStore = useUserStore()

function handleProfileUpdated(profile: any) {
  userStore.setUserInfo(profile)
}
</script>

<style scoped>
.layer { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); z-index: 99; }
.drawer { width: 600rpx; max-width: 82vw; height: 100%; background: #fff; padding: 100rpx 28rpx 30rpx; box-sizing: border-box; }
.profile { font-size: 30rpx; font-weight: 600; padding: 26rpx 10rpx; border-bottom: 1rpx solid #eee; }
.profile-name-row { display: flex; align-items: center; }
.profile-name-row > text { flex: 1; min-width: 0; color: #303133; font-size: 30rpx; font-weight: 600; }
.profile > text { display: block; color: #999; font-size: 22rpx; margin-top: 8rpx; }
.item, .logout { padding: 28rpx 14rpx; font-size: 28rpx; border-bottom: 1rpx solid #f3f3f3; }
.logout { color: #e74c3c; margin-top: 30rpx; }
</style>
