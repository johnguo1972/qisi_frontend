<template>
  <view class="page">
    <view class="header"><text class="title">知识点匹配待确认</text><button size="mini" @click="load">刷新</button></view>
    <view v-if="loading" class="empty">加载中...</view>
    <view v-else-if="!items.length" class="empty">暂无待确认匹配</view>
    <view v-for="item in items" :key="item.id" class="item">
      <view><text class="question">题目 {{ item.question_id }}</text><text class="evidence">{{ item.evidence?.matched_fields?.join('、') || '未匹配' }}</text></view>
      <text class="point">{{ item.knowledge_point?.module || '未匹配到知识点' }}</text>
      <view class="actions"><button size="mini" @click="decide(item, 'rejected')">拒绝</button><button v-if="item.knowledge_point" size="mini" type="primary" @click="decide(item, 'confirmed')">确认</button></view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onShow } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { knowledgeMatchApi } from '@/api/knowledge-matches'
const items = ref<any[]>([])
const loading = ref(false)
async function load() { loading.value = true; try { const result: any = await knowledgeMatchApi.pending(); items.value = result.data || [] } catch (error: any) { uni.showToast({ title: error?.message || '加载失败', icon: 'none' }) } finally { loading.value = false } }
async function decide(item: any, status: 'confirmed' | 'rejected') { try { await knowledgeMatchApi.confirm([{ id: item.id, status }]); items.value = items.value.filter(row => row.id !== item.id); uni.showToast({ title: status === 'confirmed' ? '已确认' : '已拒绝', icon: 'success' }) } catch (error: any) { uni.showToast({ title: error?.message || '操作失败', icon: 'none' }) } }
onShow(load)
</script>

<style scoped>
.page { min-height: 100vh; padding: 32rpx; background: #f6f8fb; }.header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24rpx; }.title { font-size: 38rpx; font-weight: 700; }.item { margin-bottom: 18rpx; padding: 24rpx; background: #fff; border-radius: 14rpx; }.question, .evidence, .point { display: block; margin-bottom: 10rpx; }.evidence { color: #6b7280; font-size: 24rpx; }.point { color: #2563eb; }.actions { display: flex; gap: 18rpx; }
.empty { padding: 100rpx 0; color: #6b7280; text-align: center; }
</style>
