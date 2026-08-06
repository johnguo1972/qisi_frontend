<template>
  <view class="stats-page">
    <view class="page-header">
      <text class="page-title">学情统计</text>
      <view v-if="classes.length" class="class-filter">
        <text class="filter-label">班级</text>
        <picker
          :range="classes"
          range-key="class_name"
          :value="selectedClassIndex"
          @change="handleClassChange"
        >
          <view class="picker-control">
            <text>{{ selectedClassName || '请选择班级' }}</text>
            <text class="picker-arrow">⌄</text>
          </view>
        </picker>
      </view>
    </view>

    <view v-if="loadingClasses" class="empty-card">加载班级中...</view>
    <view v-else-if="!classes.length" class="empty-card">暂无可查看的班级</view>
    <view v-else-if="loading" class="empty-card">加载中...</view>
    <view v-else-if="classId" class="stats-card">
      <view class="summary">
        <text>{{ stats.class_name || selectedClassName || '班级' }}</text>
        <text>作业 {{ stats.mission_count || 0 }} 个</text>
      </view>
      <view class="table-header">
        <text>学生</text>
        <text>作业完成</text>
        <text>作答次数</text>
        <text>正确率</text>
      </view>
      <view v-for="student in stats.students || []" :key="student.student_id" class="table-row">
        <text>{{ student.student_name || student.display_name || student.mobile || '-' }}</text>
        <text>{{ student.completed_count || 0 }}/{{ student.mission_count || 0 }}</text>
        <text>{{ student.attempt_count || 0 }}</text>
        <text>{{ student.accuracy || 0 }}%</text>
      </view>
      <view v-if="!(stats.students || []).length" class="empty-hint">该班级暂无学生数据</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classApi } from '@/api/institutions'
import type { UUID } from '@/types/uuid'

interface ClassOption {
  id: UUID
  class_name: string
  class_no?: string
}

const classes = ref<ClassOption[]>([])
const routeClassId = ref('')
const classId = ref<UUID | ''>('')
const loadingClasses = ref(false)
const loading = ref(false)
const stats = ref<any>({ students: [] })

const selectedClassIndex = computed(() => {
  const index = classes.value.findIndex(item => String(item.id) === String(classId.value))
  return index >= 0 ? index : 0
})

const selectedClassName = computed(() => {
  return classes.value.find(item => String(item.id) === String(classId.value))?.class_name || ''
})

// 从班级卡片进入时保留 classId；从侧边栏进入时由 initialize 默认选择第一个班级。
onLoad((options: any) => {
  routeClassId.value = String(options?.classId || '').trim()
})

// 该页面既作为独立页面使用，也作为教师布局中的内嵌组件使用，因此初始化放在 onMounted。
onMounted(async () => {
  await initialize()
})

async function initialize() {
  loadingClasses.value = true
  try {
    const res: any = await classApi.list()
    const items = res.data?.items || res.data || []
    classes.value = Array.isArray(items) ? items : []

    // 路由 classId 优先；没有路由参数时默认展示第一个班级。
    classId.value = routeClassId.value || classes.value[0]?.id || ''
    if (classId.value) await loadStats()
  } catch (e) {
    classes.value = []
    uni.showToast({ title: '加载班级失败', icon: 'none' })
  } finally {
    loadingClasses.value = false
  }
}

async function handleClassChange(event: any) {
  const index = Number(event?.detail?.value)
  const selected = classes.value[index]
  if (!selected || selected.id === classId.value) return

  classId.value = selected.id
  await loadStats()
}

async function loadStats() {
  if (!classId.value) return

  loading.value = true
  stats.value = { students: [] }
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
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.page-title { font-size: 20px; font-weight: 500; color: #303133; }
.class-filter { display: flex; align-items: center; gap: 10px; }
.filter-label { color: #606266; font-size: 14px; }
.picker-control { min-width: 180px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 4px; background: #fff; color: #303133; font-size: 14px; cursor: pointer; }
.picker-arrow { color: #909399; font-size: 16px; }
.stats-card, .empty-card { background: #fff; border-radius: 8px; padding: 20px; }
.summary, .table-header, .table-row { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 12px; align-items: center; }
.summary { margin-bottom: 18px; color: #606266; }
.table-header { padding: 12px 0; color: #909399; border-bottom: 1px solid #ebeef5; }
.table-row { padding: 14px 0; color: #303133; border-bottom: 1px solid #f2f6fc; }
.empty-card { text-align: center; color: #909399; }
.empty-hint { padding: 30px 0; text-align: center; color: #909399; }

@media (max-width: 768px) {
  .page-header { align-items: flex-start; flex-direction: column; gap: 12px; }
  .class-filter { width: 100%; }
  .class-filter picker { flex: 1; }
  .picker-control { min-width: 0; }
}
</style>
