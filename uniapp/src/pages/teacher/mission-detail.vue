<template>
  <view class="detail-page">

    <!-- 右侧内容区 -->
    <view class="main">
      <!-- 任务信息卡片 -->
      <view v-if="mission" class="mission-card">
        <text class="page-title">{{ isGrading ? '批改作业' : '作业详情' }}</text>
        <text class="mission-name">{{ mission.mission_name }}</text>
        <text class="mission-no">{{ mission.mission_no }}</text>
        <view class="status-badge" :class="mission.status">{{ statusText(mission.status) }}</view>
        <text class="mission-desc">{{ mission.goal_text || '暂无描述' }}</text>
        <view class="meta-grid">
          <view class="meta-item">
            <text class="meta-label">截止时间</text>
            <text class="meta-value">{{ mission.end_at || '未设置' }}</text>
          </view>
          <view class="meta-item">
            <text class="meta-label">关卡数</text>
            <text class="meta-value">{{ mission.level_count || 0 }}</text>
          </view>
        </view>
      </view>
      <view v-if="mission" class="action-buttons">
        <button v-if="mission.status === 'draft'" @click="publishMission" class="action-btn publish">
          发布任务
        </button>
        <button v-if="mission.status === 'published'" @click="startMission" class="action-btn start">
          开始任务
        </button>
        <button @click="cloneMission" class="action-btn clone">克隆任务</button>
        <button @click="exportPdf" class="action-btn export">导出PDF</button>
      </view>
      <view v-if="isGrading" class="grading-panel">
        <view class="panel-header"><text class="panel-title">学生提交与批改</text></view>
        <view v-if="gradingLoading" class="empty">加载提交记录中...</view>
        <view v-else-if="gradingAttempts.length === 0" class="empty">暂无学生提交</view>
        <view v-for="attempt in gradingAttempts" :key="attempt.id" class="grading-item">
          <view class="grading-question">
            <text class="grading-student">{{ studentName(attempt.student_id) }}</text>
            <text>{{ attempt.question_no || attempt.question_id }}</text>
            <text class="grading-stem">{{ attempt.stem }}</text>
          </view>
          <text class="grading-answer">学生答案：{{ answerText(attempt.answer_content) }}</text>
          <view class="grading-controls">
            <input class="score-input" type="number" v-model.number="attempt.score" placeholder="分数" />
            <input class="feedback-input" v-model="attempt.feedback" placeholder="批语（可选）" />
            <button class="save-grade-btn" @click="saveGrade(attempt)">保存批改</button>
            <button class="variant-btn" @click="generateVariant(attempt)">生成同类题</button>
          </view>
        </view>
      </view>
      <!-- 关卡列表 -->
      <view v-if="!isGrading" class="levels-panel">
        <view class="panel-header">
          <text class="panel-title">关卡列表</text>
        </view>
        <scroll-view scroll-y class="levels-list">
          <view v-for="(level, i) in levels" :key="level.id" class="level-card">
            <view class="level-header">
              <view class="level-order">
                <view class="order-dot">{{ i + 1 }}</view>
                <text class="order-text">第 {{ i + 1 }} 关</text>
              </view>
              <text class="level-type-badge">{{ levelTypeText(level.level_type) }}</text>
            </view>
            <text class="level-name">{{ level.level_name }}</text>
            <view class="level-footer">
              <text class="level-mode">{{ modeText(level.mode_policy) }}</text>
              <text class="level-questions">题目数: {{ level.question_count || 0 }}</text>
              <text class="level-practice-btn" @click="goPractice(level.id)">练习</text>
            </view>
          </view>
          <view v-if="levels.length === 0" class="empty">
            <text>暂无关卡</text>
          </view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { missionApi } from '@/api/index.ts'
import { type Mission } from '@/api/missions.ts'

const mission = ref<Mission | null>(null)
const levels = ref<any[]>([])
const missionId = ref<string>('')
const isGrading = ref(false)
const gradingLoading = ref(false)
const gradingAttempts = ref<any[]>([])
const gradingStudents = ref<any[]>([])

onLoad((options: any) => {
  const id = String(options?.id || '')
  isGrading.value = options?.mode === 'grading'
  if (!id) {
    uni.showToast({ title: '缺少任务ID', icon: 'none' })
    return
  }
  missionId.value = id
})

onMounted(async () => {
  await loadMission()
  if (isGrading.value) await loadGrading()
})

async function loadMission() {
  try {
    const res = await missionApi.detail(missionId.value)
    mission.value = res.data
    levels.value = res.data?.levels || []
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
}

async function loadGrading() {
  gradingLoading.value = true
  try {
    const res: any = await missionApi.grading(missionId.value)
    gradingStudents.value = res.data?.students || []
    gradingAttempts.value = (res.data?.attempts || []).map((item: any) => ({ ...item, feedback: item.answer_content?.teacher_feedback || '' }))
  } catch (e) {
    uni.showToast({ title: '加载批改记录失败', icon: 'none' })
  } finally { gradingLoading.value = false }
}
function studentName(id: string) { return gradingStudents.value.find(item => String(item.id) === String(id))?.name || id }
function answerText(value: any) { return typeof value === 'string' ? value : JSON.stringify(value || '') }
async function saveGrade(attempt: any) {
  try {
    await missionApi.gradeAttempt(missionId.value, attempt.id, { score: Number(attempt.score), feedback: attempt.feedback })
    uni.showToast({ title: '批改已保存', icon: 'success' })
    await loadGrading()
  } catch (e) { uni.showToast({ title: '保存批改失败', icon: 'none' }) }
}
async function generateVariant(attempt: any) {
  if (!attempt.level_id) { uni.showToast({ title: '该提交缺少关卡信息', icon: 'none' }); return }
  try {
    await missionApi.generateVariant(missionId.value, {
      question_id: attempt.question_id, level_id: attempt.level_id,
      student_id: attempt.student_id, variant_mode: '情境变化',
    })
    uni.showToast({ title: '已提交同类题生成任务，将定向给该学生', icon: 'success' })
  } catch (e) { uni.showToast({ title: '同类题生成失败', icon: 'none' }) }
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    draft: '草稿', published: '已发布', running: '进行中', closed: '已关闭', archived: '已归档'
  }
  return map[status] || status
}

function levelTypeText(type: string): string {
  const map: Record<string, string> = {
    practice: '练习', review: '复习', retry: '重做', variant: '变式', check: '检测'
  }
  return map[type] || type
}

function modeText(mode: string): string {
  const map: Record<string, string> = {
    block_a: 'Block A', allow_a: 'Allow A', require_guidance: '需引导', free_practice: '自由练习'
  }
  return map[mode] || mode
}

async function publishMission() {
  try {
    await missionApi.publish(missionId.value)
    uni.showToast({ title: '发布成功', icon: 'success' })
    await loadMission()
  } catch (e) {
    uni.showToast({ title: '发布失败', icon: 'none' })
  }
}

async function startMission() {
  try {
    await missionApi.update(missionId.value, { status: 'running' })
    uni.showToast({ title: '已开始', icon: 'success' })
    await loadMission()
  } catch (e) {
    uni.showToast({ title: '操作失败', icon: 'none' })
  }
}

async function cloneMission() {
  try {
    await missionApi.clone(missionId.value)
    uni.showToast({ title: '克隆成功', icon: 'success' })
  } catch (e) {
    uni.showToast({ title: '克隆失败', icon: 'none' })
  }
}

async function exportPdf() {
  try {
    const res: any = await missionApi.exportPdf(missionId.value)
    const url = res.data?.download_url
    if (url) {
      // H5/native callers can open the generated media URL.
      window.open?.(url, '_blank')
      uni.showToast({ title: 'PDF已生成', icon: 'success' })
    }
  } catch (e) {
    uni.showToast({ title: '导出失败', icon: 'none' })
  }
}

function goPractice(levelId: number) {
  uni.navigateTo({ url: `/pages/teacher/level-practice?missionId=${missionId.value}&levelId=${levelId}` })
}
</script>

<style scoped>
.detail-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 0;
  flex: 1;
  padding: 30rpx 40rpx;
}
.mission-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 32rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  margin-bottom: 20rpx;
}
.page-title {
  display: block;
  margin-bottom: 18rpx;
  font-size: 30rpx;
  font-weight: bold;
  color: #303133;
}
.mission-name {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 6rpx;
}
.mission-no {
  font-size: 22rpx;
  color: #999;
  display: block;
}
.status-badge {
  display: inline-block;
  font-size: 22rpx;
  padding: 4rpx 16rpx;
  border-radius: 4rpx;
  margin-top: 12rpx;
}
.status-badge.draft { background: #f0f0f0; color: #666; }
.status-badge.published { background: #e3f2fd; color: #2196f3; }
.status-badge.running { background: #e8f5e9; color: #4caf50; }
.status-badge.closed { background: #fff3e0; color: #ff9800; }
.status-badge.archived { background: #f5f5f5; color: #999; }
.mission-desc {
  font-size: 24rpx;
  color: #666;
  margin-top: 16rpx;
  display: block;
  line-height: 1.6;
}
.grading-panel { background: #fff; border-radius: 12rpx; padding: 24rpx; margin-bottom: 20rpx; }
.grading-item { padding: 20rpx 0; border-bottom: 1rpx solid #eee; }
.grading-question { display: flex; gap: 14rpx; align-items: flex-start; flex-wrap: wrap; color: #555; }
.grading-student { color: #409eff; font-weight: bold; }
.grading-stem { width: 100%; color: #333; white-space: normal; overflow-wrap: anywhere; }
.grading-answer { display: block; margin: 14rpx 0; color: #666; white-space: normal; overflow-wrap: anywhere; }
.grading-controls { display: flex; gap: 12rpx; align-items: center; }
.score-input { width: 110rpx; border: 1rpx solid #ddd; padding: 10rpx; }
.feedback-input { flex: 1; border: 1rpx solid #ddd; padding: 10rpx; }
.save-grade-btn { background: #409eff; color: #fff; font-size: 22rpx; margin: 0; }
.variant-btn { background: #67c23a; color: #fff; font-size: 22rpx; margin: 0; }
.meta-grid {
  display: flex;
  gap: 16rpx;
  margin-top: 20rpx;
}
.meta-item {
  flex: 1;
  background: #fff;
  padding: 12rpx;
  border-radius: 6rpx;
}
.meta-label {
  font-size: 20rpx;
  color: #999;
  display: block;
}
.meta-value {
  font-size: 22rpx;
  color: #333;
  display: block;
  margin-top: 4rpx;
}
.action-buttons {
  display: flex;
  flex-direction: row;
  justify-content: flex-end;
  align-items: center;
  gap: 10rpx;
  width: 100%;
  margin: 0 0 20rpx;
}
.action-btn {
  width: auto;
  min-width: 0;
  height: 52rpx;
  line-height: 52rpx;
  margin: 0;
  padding: 0 18rpx;
  box-sizing: border-box;
  white-space: nowrap;
  font-size: 22rpx;
  border-radius: 8rpx;
  color: #fff;
}
.publish { background: #4caf50; }
.start { background: #ff9800; }
.clone { background: #409eff; }
.export {
  color: #606266;
  background: #f5f7fa;
  border: 1rpx solid #cfd3dc;
}
.levels-panel {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.panel-header {
  margin-bottom: 20rpx;
}
.panel-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}
.levels-list {
  max-height: 500px;
}
.level-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.level-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12rpx;
}
.level-order {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.order-dot {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
}
.order-text {
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
}
.level-type-badge {
  font-size: 22rpx;
  color: #409eff;
  background: #ecf5ff;
  padding: 4rpx 16rpx;
  border-radius: 4rpx;
}
.level-name {
  font-size: 24rpx;
  color: #666;
  display: block;
  margin-bottom: 12rpx;
}
.level-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.level-mode {
  font-size: 22rpx;
  color: #666;
}
.level-questions {
  font-size: 22rpx;
  color: #999;
}
.level-practice-btn {
  font-size: 22rpx;
  color: #fff;
  background: #4caf50;
  padding: 6rpx 20rpx;
  border-radius: 6rpx;
  cursor: pointer;
}
.level-practice-btn:hover {
  background: #43a047;
}
.empty {
  text-align: center;
  padding: 80rpx;
  color: #999;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .main {
    margin-left: 60px;
    padding: 20rpx;
  }
}
</style>
