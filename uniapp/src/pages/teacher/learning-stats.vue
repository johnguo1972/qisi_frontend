<template>
  <view class="stats-page">
    <view class="page-header"><text class="page-title">学情统计</text></view>
    <view v-if="loading" class="empty-card">加载中...</view>
    <view v-else-if="classId" class="stats-card">
      <view class="summary"><text>{{ stats.class_name || '班级' }}</text><text>作业 {{ stats.mission_count || 0 }} 个</text></view>
      <view class="table-header"><text>学生</text><text>作业完成</text><text>作答次数</text><text>正确率</text></view>
      <view v-for="student in stats.students || []" :key="student.student_id" class="table-row">
        <text>{{ student.student_name || student.display_name || student.mobile || '-' }}</text>
        <text>{{ student.completed_count || 0 }}/{{ student.mission_count || 0 }}</text>
        <text>{{ student.attempt_count || 0 }}</text>
        <text>{{ student.accuracy || 0 }}%</text>
      </view>
      <view v-if="!(stats.students || []).length" class="empty-hint">该班级暂无学生数据</view>
    </view>
    <view v-else class="empty-card"><text>请从班级管理进入学情统计</text></view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classApi } from '@/api/institutions'

const classId = ref('')
const loading = ref(false)
const stats = ref<any>({ students: [] })

onLoad(async (options: any) => {
  classId.value = String(options?.classId || '')
  if (classId.value) await loadStats()
})

async function loadStats() {
  loading.value = true
  try {
    const res: any = await classApi.learningStats(classId.value)
    stats.value = res.data || { students: [] }
  } catch (e) {
    uni.showToast({ title: '加载学情失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.stats-page { min-height: 100vh; padding: 24px; background: #f5f7fa; box-sizing: border-box; }
.page-header { display: flex; align-items: center; margin-bottom: 24px; }
.page-title { font-size: 20px; font-weight: 500; color: #303133; }
.stats-card, .empty-card { background: #fff; border-radius: 8px; padding: 20px; }
.summary, .table-header, .table-row { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 12px; align-items: center; }
.summary { margin-bottom: 18px; color: #606266; }
.table-header { padding: 12px 0; color: #909399; border-bottom: 1px solid #ebeef5; }
.table-row { padding: 14px 0; color: #303133; border-bottom: 1px solid #f2f6fc; }
.empty-card { text-align: center; color: #909399; }
.empty-hint { padding: 30px 0; text-align: center; color: #909399; }
</style>
