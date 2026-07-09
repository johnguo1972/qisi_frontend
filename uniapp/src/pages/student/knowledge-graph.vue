<template>
  <view class="kg-page">
    <view class="nav"><text class="title">知识掌握度</text></view>
    <view v-if="loading" class="hint">加载中...</view>
    <view v-else-if="!items.length" class="hint">暂无作答数据，先去做几道题吧～</view>
    <view v-else class="list">
      <view v-for="it in items" :key="it.knowledge" class="card">
        <view class="row">
          <text class="kp">{{ it.knowledge }}</text>
          <text :class="['badge', it.mastery]">{{ masteryLabel(it.mastery) }}</text>
        </view>
        <view class="bar"><view class="bar-inner" :style="{ width: it.accuracy + '%' }" :class="it.mastery"></view></view>
        <text class="meta">正确率 {{ it.accuracy }}% · 作答 {{ it.attempt }} · 正确 {{ it.correct }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { studentApi } from '@/api/student.ts'

const items = ref<any[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await studentApi.knowledgeMastery()
    items.value = res.data?.items || []
  } finally { loading.value = false }
})

function masteryLabel(m: string) {
  return ({ mastered: '已掌握', reviewing: '巩固中', weak: '薄弱' } as Record<string,string>)[m] || m
}
</script>

<style scoped>
.kg-page { min-height:100vh; background:#f0f2f5; }
.nav { padding:24rpx 32rpx; background:#fff; border-bottom:1rpx solid #eee; }
.title { font-size:32rpx; font-weight:bold; }
.hint { text-align:center; color:#999; padding:160rpx 0; font-size:26rpx; }
.list { padding:24rpx; }
.card { background:#fff; border-radius:12rpx; padding:24rpx; margin-bottom:20rpx; }
.row { display:flex; justify-content:space-between; align-items:center; margin-bottom:16rpx; }
.kp { font-size:28rpx; font-weight:bold; color:#333; }
.badge { font-size:22rpx; padding:4rpx 16rpx; border-radius:20rpx; }
.badge.mastered{background:#e8f5e9;color:#4caf50;}
.badge.reviewing{background:#fff3e0;color:#ff9800;}
.badge.weak{background:#ffebee;color:#f44336;}
.bar { height:12rpx; background:#eee; border-radius:6rpx; overflow:hidden; margin-bottom:12rpx; }
.bar-inner { height:100%; }
.bar-inner.mastered{background:#4caf50;} .bar-inner.reviewing{background:#ff9800;} .bar-inner.weak{background:#f44336;}
.meta { font-size:22rpx; color:#999; }
</style>
