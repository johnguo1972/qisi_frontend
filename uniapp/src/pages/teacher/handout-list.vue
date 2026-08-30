<template>
  <view class="page">
    <view class="header"><text class="title">讲义管理</text><button size="mini" @click="load">刷新</button></view>
    <view v-if="!items.length" class="empty">暂无讲义，请从题库勾选题目后创建</view>
    <view v-for="item in items" :key="item.id" class="item">
      <view><text class="name">{{ item.name }}</text><text class="meta">{{ item.status }} · {{ item.question_count }} 道题 · {{ item.course_name || '未关联课程' }}</text></view>
      <button size="mini" @click="open(item.id)">查看</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { handoutApi } from '@/api/handouts'
const items = ref<any[]>([])
async function load() { try { const result: any = await handoutApi.list(); items.value = result.data || [] } catch (error: any) { uni.showToast({ title: error?.message || '加载失败', icon: 'none' }) } }
function open(id: string) { uni.navigateTo({ url: `/pages/teacher/handout-create?handoutId=${id}` }) }
onShow(load)
</script>

<style scoped>
.page { min-height: 100vh; padding: 32rpx; background: #f6f8fb; }.header, .item { display: flex; align-items: center; justify-content: space-between; }.header { margin-bottom: 24rpx; }.title { font-size: 38rpx; font-weight: 700; }.item { margin-bottom: 18rpx; padding: 24rpx; background: #fff; border-radius: 14rpx; }.name, .meta { display: block; }.name { margin-bottom: 8rpx; font-size: 30rpx; font-weight: 600; }.meta, .empty { color: #6b7280; font-size: 24rpx; }.empty { padding: 100rpx 0; text-align: center; }
</style>
