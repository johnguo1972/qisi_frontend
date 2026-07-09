<template>
  <view class="workbench">
    <TeacherSidebar activeItem="missions" />

    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">任务列表</text>
        <button class="create-btn" @click="goCreate">+ 创建任务</button>
      </view>

      <!-- 筛选栏 -->
      <view class="filter-bar">
        <view class="filter-item">
          <text class="filter-label">班级</text>
          <picker :range="classList" range-key="class_name" @change="onClassFilterChange" :value="classFilterIndex">
            <view class="filter-value">{{ classFilterText }}</view>
          </picker>
        </view>
        <view class="filter-item">
          <text class="filter-label">状态</text>
          <picker :range="statusOptions" @change="onStatusFilterChange" :value="statusFilterIndex">
            <view class="filter-value">{{ statusFilterText }}</view>
          </picker>
        </view>
        <view class="filter-item">
          <text class="filter-label">排序</text>
          <picker :range="sortOptions" @change="onSortChange" :value="sortIndex">
            <view class="filter-value">{{ sortText }}</view>
          </picker>
        </view>
        <view class="filter-actions">
          <button class="filter-reset-btn" @click="resetFilters">重置</button>
        </view>
      </view>

      <!-- 任务列表（表格形式） -->
      <view v-if="loading" class="loading">加载中...</view>
      <view v-else-if="filteredMissions.length === 0" class="empty">
        <text>还没有任务，点击"创建任务"开始</text>
      </view>
      <view v-else class="table-container">
        <!-- 表头 -->
        <view class="table-header">
          <text class="col col-name">任务名称</text>
          <text class="col col-class">班级</text>
          <text class="col col-questions">题目数</text>
          <text class="col col-levels">关卡数</text>
          <text class="col col-start">开始时间</text>
          <text class="col col-end">截止日期</text>
          <text class="col col-status">状态</text>
          <text class="col col-actions">操作</text>
        </view>
        <!-- 表格内容 -->
        <scroll-view scroll-y class="table-body">
          <view v-for="m in filteredMissions" :key="m.id" class="table-row">
            <text class="col col-name" @click="goMissionDetail(m.id)">{{ m.mission_name }}</text>
            <text class="col col-class">{{ m.class_name || '-' }}</text>
            <text class="col col-questions">{{ m.question_count || 0 }}</text>
            <text class="col col-levels">{{ m.level_count || 0 }}</text>
            <text class="col col-start">{{ formatDate(m.start_at) }}</text>
            <text class="col col-end">{{ formatDate(m.end_at) }}</text>
            <view class="col col-status">
              <text class="status-badge" :class="'status-' + m.status">{{ statusText(m.status) }}</text>
            </view>
            <view class="col col-actions">
              <text class="action-btn action-view" @click="goMissionDetail(m.id)">查看</text>
              <text class="action-btn action-edit" @click="goEdit(m.id)">编辑</text>
              <text v-if="m.status === 'draft'" class="action-btn action-delete" @click="confirmDelete(m)">删除</text>
            </view>
          </view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { missionApi, type Mission } from '@/api/missions.ts'
import { classApi } from '@/api/institutions.ts'
import TeacherSidebar from '@/components/TeacherSidebar.vue'

interface MissionExtended extends Mission {
  class_name?: string
  class_obj?: number
  question_count?: number
}

const missions = ref<MissionExtended[]>([])
const classList = ref<any[]>([])
const loading = ref(false)

// 筛选状态
const classFilterIndex = ref(0)
const statusFilterIndex = ref(0)
const sortIndex = ref(0)

// 选项
const statusOptions = ['全部状态', '草稿', '已发布', '进行中', '已关闭', '已归档']
const sortOptions = ['创建时间 ↓', '创建时间 ↑', '截止日期 ↑', '截止日期 ↓']

onMounted(async () => {
  await loadClasses()
  await loadMissions()
})

async function loadClasses() {
  try {
    const res: any = await classApi.simpleList()
    classList.value = [{ id: 0, class_name: '全部班级' }, ...(res.data?.data || res.data || [])]
  } catch (e) {
    classList.value = [{ id: 0, class_name: '全部班级' }]
  }
}

async function loadMissions() {
  loading.value = true
  try {
    const res = await missionApi.list()
    missions.value = res.data || []
  } catch (e) {
    console.error('Failed to load missions:', e)
  } finally {
    loading.value = false
  }
}

// 计算属性
const classFilterText = computed(() => {
  const cls = classList.value[classFilterIndex.value]
  return cls ? cls.class_name : '全部班级'
})

const statusFilterText = computed(() => statusOptions[statusFilterIndex.value] || '全部状态')

const sortText = computed(() => sortOptions[sortIndex.value])

const statusMap: Record<string, string> = {
  '全部状态': '', '草稿': 'draft', '已发布': 'published',
  '进行中': 'running', '已关闭': 'closed', '已归档': 'archived'
}

const filteredMissions = computed(() => {
  let list = [...missions.value]

  // 班级筛选
  const classFilter = classList.value[classFilterIndex.value]
  if (classFilter && classFilter.id !== 0) {
    list = list.filter(m => m.class_obj === classFilter.id)
  }

  // 状态筛选
  const statusFilter = statusMap[statusOptions[statusFilterIndex.value]]
  if (statusFilter) {
    list = list.filter(m => m.status === statusFilter)
  }

  // 排序
  switch (sortIndex.value) {
    case 0: // 创建时间 ↓ (默认，按 id 降序)
      list.sort((a, b) => b.id - a.id)
      break
    case 1: // 创建时间 ↑
      list.sort((a, b) => a.id - b.id)
      break
    case 2: // 截止日期 ↑
      list.sort((a, b) => (a.end_at || '9999').localeCompare(b.end_at || '9999'))
      break
    case 3: // 截止日期 ↓
      list.sort((a, b) => (b.end_at || '9999').localeCompare(a.end_at || '9999'))
      break
  }

  return list
})

function statusText(status: string): string {
  const map: Record<string, string> = {
    draft: '草稿', published: '已发布', running: '进行中',
    closed: '已关闭', archived: '已归档'
  }
  return map[status] || status
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return dateStr
  }
}

// 筛选事件
function onClassFilterChange(e: any) { classFilterIndex.value = e.detail.value }
function onStatusFilterChange(e: any) { statusFilterIndex.value = e.detail.value }
function onSortChange(e: any) { sortIndex.value = e.detail.value }

function resetFilters() {
  classFilterIndex.value = 0
  statusFilterIndex.value = 0
  sortIndex.value = 0
}

// 导航
function goMissionDetail(id: number) { uni.navigateTo({ url: `/pages/teacher/mission-detail?id=${id}` }) }
function goEdit(id: number) { uni.navigateTo({ url: `/pages/teacher/mission-create?id=${id}` }) }
function goCreate() { uni.navigateTo({ url: '/pages/teacher/mission-create' }) }

// 删除任务
function confirmDelete(m: MissionExtended) {
  uni.showModal({
    title: '确认删除',
    content: `确定要删除任务"${m.mission_name}"吗？此操作不可撤销。`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await missionApi.remove(m.id)
          uni.showToast({ title: '删除成功', icon: 'success' })
          await loadMissions()
        } catch (e: any) {
          const msg = e?.data?.message || '删除失败'
          uni.showToast({ title: msg, icon: 'none' })
        }
      }
    },
  })
}
</script>

<style scoped>
.workbench {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 240px;
  flex: 1;
  padding: 30rpx 40rpx;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10rpx 0 30rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.create-btn {
  padding: 12rpx 32rpx;
  background: #4caf50;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  font-size: 26rpx;
  height: auto;
  line-height: normal;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  align-items: flex-end;
  gap: 24rpx;
  padding: 20rpx 24rpx;
  background: #fff;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  flex-wrap: wrap;
}
.filter-item {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.filter-label {
  font-size: 22rpx;
  color: #666;
}
.filter-value {
  padding: 10rpx 20rpx;
  background: #f5f5f5;
  border: 1rpx solid #ddd;
  border-radius: 6rpx;
  font-size: 24rpx;
  color: #333;
  min-width: 160rpx;
  text-align: center;
}
.filter-actions {
  margin-left: auto;
}
.filter-reset-btn {
  padding: 10rpx 24rpx;
  background: #fff;
  color: #666;
  border: 1rpx solid #ddd;
  border-radius: 6rpx;
  font-size: 24rpx;
  height: auto;
  line-height: normal;
}

/* 表格容器 */
.table-container {
  background: #fff;
  border-radius: 12rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

/* 表头 */
.table-header {
  display: flex;
  align-items: center;
  padding: 16rpx 20rpx;
  background: #f5f7fa;
  border-bottom: 1rpx solid #eee;
  font-size: 22rpx;
  font-weight: bold;
  color: #666;
}

/* 表格内容 */
.table-body {
  max-height: 70vh;
}
.table-row {
  display: flex;
  align-items: center;
  padding: 16rpx 20rpx;
  border-bottom: 1rpx solid #f0f0f0;
  font-size: 24rpx;
  transition: background 0.15s;
}
.table-row:hover {
  background: #f9f9f9;
}
.table-row:last-child {
  border-bottom: none;
}

/* 列宽 */
.col { padding: 0 8rpx; }
.col-name { flex: 2; color: #333; font-weight: 500; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.col-name:hover { color: #409eff; }
.col-class { flex: 1; color: #666; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.col-questions { width: 80rpx; text-align: center; color: #666; }
.col-levels { width: 80rpx; text-align: center; color: #666; }
.col-start { width: 140rpx; text-align: center; color: #666; font-size: 22rpx; }
.col-end { width: 140rpx; text-align: center; color: #666; font-size: 22rpx; }
.col-status { width: 100rpx; text-align: center; }
.col-actions { width: 120rpx; display: flex; gap: 8rpx; justify-content: center; }

/* 状态标签 */
.status-badge {
  display: inline-block;
  padding: 4rpx 12rpx;
  border-radius: 4rpx;
  font-size: 20rpx;
}
.status-draft { background: #f0f0f0; color: #666; }
.status-published { background: #e3f2fd; color: #2196f3; }
.status-running { background: #e8f5e9; color: #4caf50; }
.status-closed { background: #fff3e0; color: #ff9800; }
.status-archived { background: #f5f5f5; color: #999; }

/* 操作按钮 */
.action-btn {
  font-size: 22rpx;
  padding: 4rpx 8rpx;
  border-radius: 4rpx;
  cursor: pointer;
  transition: background 0.15s;
}
.action-view { color: #409eff; }
.action-view:hover { background: #ecf5ff; }
.action-edit { color: #ff9800; }
.action-edit:hover { background: #fff3e0; }
.action-delete { color: #f44336; }
.action-delete:hover { background: #ffebee; }

/* 加载和空状态 */
.loading, .empty {
  text-align: center;
  padding: 100rpx;
  color: #999;
  font-size: 26rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .main { margin-left: 60px; padding: 20rpx; }
  .filter-bar { flex-direction: column; align-items: stretch; }
  .filter-actions { margin-left: 0; }
  .table-header, .table-row { font-size: 20rpx; }
  .col-start, .col-end { display: none; }
}
</style>
