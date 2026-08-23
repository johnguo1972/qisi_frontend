<template>
  <view v-if="roles.length > 1" class="role-switcher">
    <text class="switcher-label">切换身份</text>
    <view class="role-options">
      <button
        v-for="role in roles"
        :key="role"
        class="role-option"
        :class="{ active: role === userInfo.active_role }"
        :disabled="switching || role === userInfo.active_role"
        @click="switchToRole(role)"
      >{{ roleLabel(role) }}</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { authApi } from '@/api/index.ts'
import { useUserStore } from '@/store/index.ts'
import { persistSession, routeForRole, type AppRole } from '@/utils/roles'

const userStore = useUserStore()
const switching = ref(false)
const userInfo = computed(() => userStore.userInfo || uni.getStorageSync('userInfo') || {})
const roles = computed<AppRole[]>(() =>
  Array.isArray(userInfo.value.roles) ? userInfo.value.roles : []
)

function roleLabel(role: AppRole): string {
  return { admin: '管理员', teacher: '教师', parent: '家长', student: '学生' }[role]
}

async function switchToRole(role: AppRole) {
  if (switching.value || role === userInfo.value.active_role) return
  switching.value = true
  try {
    const res = await authApi.switchRole(role)
    if (res.code !== 0 || !res.data) {
      uni.showToast({ title: res.message || '身份切换失败', icon: 'none' })
      return
    }
    persistSession(res.data)
    userStore.setUserInfo(res.data.user)
    uni.reLaunch({ url: routeForRole(res.data.user.active_role as AppRole) })
  } catch (e: any) {
    uni.showToast({ title: e?.message || '身份切换失败', icon: 'none' })
  } finally {
    switching.value = false
  }
}
</script>

<style scoped>
.role-switcher { margin-top: 16rpx; }
.switcher-label { display: block; margin-bottom: 8rpx; font-size: 20rpx; color: #999; }
.role-options { display: flex; flex-wrap: wrap; gap: 8rpx; }
.role-option { margin: 0; padding: 4rpx 12rpx; border: 1rpx solid #dcdfe6; border-radius: 8rpx; background: #fff; color: #606266; font-size: 20rpx; line-height: 1.6; }
.role-option.active { border-color: #409eff; background: #ecf5ff; color: #409eff; }
.role-option[disabled]:not(.active) { opacity: .5; }
</style>
