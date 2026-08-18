<template>
  <view class="nav">
    <view v-for="item in items" :key="item.key" class="nav-item" :class="{ active: active === item.key }" @click="go(item.key)">
      <text class="nav-icon">{{ item.icon }}</text>
      <text>{{ item.label }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
const props = defineProps<{ active: string }>()
const items = [
  { key: 'home', label: '学习概览', icon: '📊', path: '/pages/parent/home' },
  { key: 'children', label: '孩子管理', icon: '👨‍👩‍👧', path: '/pages/parent/bind' },
  { key: 'wrongbook', label: '错题分析', icon: '📝', path: '/pages/parent/wrongbook' },
  { key: 'growth', label: '成长分析', icon: '📈', path: '/pages/parent/growth' },
  { key: 'knowledge', label: '知识掌握', icon: '🧠', path: '/pages/parent/knowledge' },
]

function go(key: string) {
  const item = items.find(value => value.key === key)
  if (!item || item.key === props.active) return
  uni.navigateTo({ url: item.path })
}

</script>

<style scoped>
.nav { display: flex; gap: 12rpx; margin: 18rpx 0; padding: 10rpx; overflow-x: auto; background: #fff; border-radius: 16rpx; }
.nav-item { flex: 0 0 auto; min-width: 126rpx; padding: 14rpx 10rpx; border-radius: 12rpx; color: #606266; text-align: center; font-size: 22rpx; white-space: nowrap; }
.nav-icon { display: block; margin-bottom: 6rpx; font-size: 30rpx; }
.nav-item.active { color: #409eff; background: #ecf5ff; }
</style>
