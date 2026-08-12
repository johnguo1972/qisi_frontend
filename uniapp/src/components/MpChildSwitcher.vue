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

const props = defineProps<{ visible?: boolean }>()
const emit = defineEmits<{ changed: [child: any] }>()
const children = ref<any[]>([])
const selected = ref<any>(null)
const loading = ref(false)
const visible = computed(() => props.visible !== false)
const currentName = computed(() => selected.value?.display_name || '')

async function load() {
  if (!visible.value) return
  const res: any = await parentApi.children()
  children.value = Array.isArray(res.data) ? res.data : []
  const saved = uni.getStorageSync('activeChildId')
  selected.value = children.value.find(child => String(child.id) === String(saved)) || children.value[0] || null
  if (selected.value) await setContext(selected.value, false)
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
</script>

<style scoped>
.switcher { margin: 18rpx 22rpx 0; padding: 18rpx 24rpx; background: #fff; border-radius: 16rpx; }
.current { color: #409eff; font-size: 26rpx; }
.hint { display: block; margin-top: 8rpx; color: #999; font-size: 22rpx; }
</style>
