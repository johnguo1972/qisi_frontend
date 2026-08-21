<template>
  <view v-if="visible" class="switcher">
    <picker :range="children" range-key="display_name" @change="onChange">
      <view class="current">当前：{{ currentName || '请选择孩子' }} ▼</view>
    </picker>
    <text v-if="loading" class="hint">切换中...</text>
    <text v-else-if="!children.length" class="hint">暂无已绑定孩子</text>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { parentApi } from '@/api/index'
// #ifdef MP-WEIXIN
import { authApi } from '@/api/index'
import { useUserStore } from '@/store/index'
import { persistSession } from '@/utils/roles'
// #endif

const props = defineProps<{ visible?: boolean }>()
const emit = defineEmits<{ changed: [child: any] }>()
const children = ref<any[]>([])
const selected = ref<any>(null)
const loading = ref(false)
const visible = computed(() => props.visible !== false)
const currentName = computed(() => selected.value?.display_name || '')

// #ifdef MP-WEIXIN
/**
 * 同一账号同时拥有学生、家长身份时，学生身份本身就是可代理的对象，
 * 不需要额外创建一条家长-学生绑定记录。后端会返回该对象；这里保留
 * 本地兜底是为了兼容小程序缓存中的旧会话，以及接口升级期间的旧服务。
 */
function localSelfChild() {
  const user = uni.getStorageSync('userInfo') || {}
  const roles = Array.isArray(user.roles) ? user.roles : []
  const canUseSelf = roles.includes('parent') && roles.includes('student')
  if (!canUseSelf || !user.id) return null
  return {
    id: user.id,
    display_name: user.display_name || '当前账号',
    grade_level: user.grade_level || null,
    is_self: true,
    relation_type: 'self',
  }
}
// #endif

// #ifdef MP-WEIXIN
async function ensureParentSession() {
  const user = uni.getStorageSync('userInfo') || {}
  if (user.active_role === 'parent') return
  const roles = Array.isArray(user.roles) ? user.roles : []
  if (!roles.includes('parent')) return

  const response: any = await authApi.switchRole('parent')
  if (response?.code !== 0 || !response?.data?.user) {
    throw new Error(response?.message || '家长身份切换失败')
  }
  persistSession(response.data)
  useUserStore().setUserInfo(response.data.user)
}
// #endif

async function load() {
  if (!visible.value) return
  // #ifdef MP-WEIXIN
  // 防止旧页面缓存仍携带学生令牌，导致 /parent/context 被后端拒绝。
  await ensureParentSession()
  // #endif
  const res: any = await parentApi.children()
  // #ifdef MP-WEIXIN
  const remoteChildren = Array.isArray(res?.data) ? res.data : []
  const selfChild = localSelfChild()
  // 仅在接口明确没有返回绑定对象时使用自身身份兜底，不覆盖真实绑定列表。
  children.value = remoteChildren.length ? remoteChildren : (selfChild ? [selfChild] : [])
  // #endif
  // #ifndef MP-WEIXIN
  children.value = Array.isArray(res.data) ? res.data : []
  // #endif
  const saved = uni.getStorageSync('activeChildId')
  selected.value = children.value.find(child => String(child.id) === String(saved)) || children.value[0] || null
  if (selected.value) await setContext(selected.value)
}

async function setContext(child: any, notify = true) {
  loading.value = true
  try {
    const res: any = await parentApi.setContext(String(child.id))
    if (res.code !== 0) throw new Error(res.message || '孩子切换失败')
    selected.value = child
    uni.setStorageSync('activeChildId', String(child.id))
    if (notify) emit('changed', child)
  } finally {
    loading.value = false
  }
}

async function onChange(event: any) {
  const child = children.value[Number(event.detail.value)]
  if (!child || String(child.id) === String(selected.value?.id)) return
  try { await setContext(child) } catch (error: any) { uni.showToast({ title: error.message || '孩子切换失败', icon: 'none' }) }
}

onMounted(() => load().catch((error: any) => uni.showToast({ title: error.message || '孩子列表加载失败', icon: 'none' })))

defineExpose({ load })
</script>

<style scoped>
.switcher { margin: 18rpx 22rpx 0; padding: 18rpx 24rpx; background: #fff; border-radius: 16rpx; }
.current { color: #409eff; font-size: 26rpx; }
.hint { display: block; margin-top: 8rpx; color: #999; font-size: 22rpx; }
</style>
