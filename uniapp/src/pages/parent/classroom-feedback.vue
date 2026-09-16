<template>
  <ParentShell active-item="home">
    <view class="page">
      <view class="header">
        <text class="title">课堂错题反馈</text>
        <text class="subtitle">班级整体情况及当前绑定孩子的个人反馈</text>
      </view>
      <MpChildSwitcher ref="childSwitcher" :visible="true" @changed="onChildChanged" />
      <view v-if="loading" class="card state">正在加载反馈...</view>
      <view v-else-if="errorMessage" class="card state">{{ errorMessage }}</view>
      <view v-else-if="!data?.feedback_available" class="card state">老师尚未发布可查看的课堂反馈。</view>
      <template v-else>
        <view class="card">
          <text class="title-small">{{ data.report.mission_name }}</text>
          <text class="meta">班级：{{ data.report.class_name }}　参考人数：{{ data.report.participant_count }}人　统计题量：{{ data.report.question_count }}题</text>
          <text class="meta">累计错题：{{ data.report.total_wrong_count }}次　人均错题：{{ data.report.average_wrong_count }}道</text>
        </view>

        <view class="card">
          <text class="section-title">班级整体掌握情况</text>
          <view class="data-table">
            <view class="data-table-row data-table-header"><text>知识点</text><text>错误次数</text><text>错误率</text><text>掌握情况</text></view>
            <view v-for="item in data.knowledge_stats || []" :key="item.knowledge_key" class="data-table-row">
              <text>{{ item.knowledge_name }}</text>
              <text>{{ item.wrong_count }}次</text>
              <text :class="{ danger: Number(item.error_rate) >= 50 }">{{ item.error_rate }}%</text>
              <text>{{ masteryText(item.mastery_level) }}</text>
            </view>
          </view>
          <text v-if="!(data.knowledge_stats || []).length" class="empty-row">暂无知识点统计</text>
        </view>

        <view class="card">
          <view class="section-line">
            <text class="section-title">班级题目错误情况</text>
            <text class="section-tip">展示错误率较高的题目</text>
          </view>
          <view class="data-table">
            <view class="data-table-row data-table-header"><text>讲义/节点·题号</text><text>知识点</text><text>错误人数</text><text>错误率</text></view>
            <view v-for="item in data.high_error_questions || []" :key="item.source_question_id" class="data-table-row">
              <text>{{ questionLabel(item) }}</text>
              <text>{{ (item.knowledge_points || []).join('、') || '待归类题目' }}</text>
              <text>{{ item.wrong_count }}人</text>
              <text :class="{ danger: Number(item.wrong_rate) >= 50 }">{{ item.wrong_rate }}%</text>
            </view>
          </view>
          <text v-if="!(data.high_error_questions || []).length" class="empty-row">暂无错题统计</text>
        </view>

        <view v-if="data.student_feedback" class="card">
          <text class="section-title">{{ data.student_feedback.student_name }}的错题反馈</text>
          <view class="student-feedback-table">
            <view class="student-table-row student-table-header"><text>项目</text><text>内容</text></view>
            <view class="student-table-row"><text>错题（{{ data.student_feedback.wrong_count }}道）</text><text>{{ studentWrongQuestionText(data.student_feedback) }}</text></view>
            <view class="student-table-row"><text>涉及板块</text><text>{{ knowledgeText(data.student_feedback) }}</text></view>
            <view class="student-table-row"><text>核心错误知识点</text><text>{{ coreKnowledgeText(data.student_feedback) }}</text></view>
            <view class="student-table-row"><text>重练安排</text><text>{{ (data.student_feedback.review_arrangement || []).join('；') || '请结合错题完成订正和重练。' }}</text></view>
          </view>
          <text class="student-meta">反馈话术</text>
          <view class="script-box">{{ data.student_feedback.feedback_text || '暂无反馈话术' }}</view>
        </view>
      </template>
    </view>
  </ParentShell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import ParentShell from '@/components/ParentShell.vue'
import MpChildSwitcher from '@/components/MpChildSwitcher.vue'
import { parentApi } from '@/api/index'
import { ensurePageRole } from '@/utils/roles'

const childSwitcher = ref<any>(null)
const data = ref<any>(null)
const missionId = ref('')
const loading = ref(false)
const errorMessage = ref('')

async function onChildChanged() { await load() }

async function load() {
  if (!missionId.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    const response: any = await parentApi.classroomFeedback(missionId.value)
    if (response?.code !== undefined && response.code !== 0) throw new Error(response.message || '反馈加载失败')
    data.value = response?.data || null
  } catch (error: any) {
    errorMessage.value = error?.message || '反馈加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function masteryText(value: string): string {
  return ({ good: '掌握较好', attention: '基本掌握，需巩固', weak: '薄弱，需重点训练' } as Record<string, string>)[value] || '待关注'
}

function questionLabel(item: any): string {
  return `${item.node_name || '未分节点'}·第${item.question_no}题`
}

function studentWrongQuestionText(student: any): string {
  if (student.wrong_questions?.length) {
    return student.wrong_questions.map((item: any) => questionLabel(item)).join('、')
  }
  return student.wrong_question_nos?.length ? student.wrong_question_nos.join('、') : '无'
}

function knowledgeText(student: any): string {
  return student.knowledge_summary?.join('、') || '待归类题目'
}

function coreKnowledgeText(student: any): string {
  const points = (student.knowledge_summary || []).filter((item: string) => item !== '待归类题目')
  return points.join('、') || '待归类题目（请结合题干、解析和答案归纳）'
}

onLoad((options: any) => { missionId.value = String(options?.mission_id || '') })
onShow(() => { if (ensurePageRole('parent')) childSwitcher.value?.load?.() })
</script>

<style scoped>
.page { min-height: 100vh; padding: 28rpx 22rpx 60rpx; background: #f0f2f5; }
.header { margin-bottom: 22rpx; }.title { display: block; color: #303133; font-size: 38rpx; font-weight: 700; }.subtitle, .meta, .section-tip, .student-meta { display: block; margin-top: 10rpx; color: #909399; font-size: 23rpx; line-height: 1.7; }
.card { margin-bottom: 20rpx; padding: 26rpx; border-radius: 16rpx; background: #fff; box-shadow: 0 2rpx 12rpx #0000000d; }.state { color: #606266; text-align: center; }.title-small, .section-title { display: block; color: #1265bd; font-size: 29rpx; font-weight: 700; }.section-title { margin-bottom: 15rpx; }.section-line { display: flex; align-items: baseline; justify-content: space-between; gap: 16rpx; }.section-tip { margin: 0; }
.data-table { overflow: hidden; border: 1rpx solid #d9dfe7; border-radius: 4rpx; }.data-table-row { display: grid; grid-template-columns: 1.35fr .8fr .8fr 1.1fr; color: #606266; font-size: 23rpx; line-height: 1.6; border-top: 1rpx solid #d9dfe7; }.data-table-row:first-child { border-top: none; }.data-table-row > text { min-width: 0; padding: 16rpx; word-break: break-all; border-left: 1rpx solid #d9dfe7; }.data-table-row > text:first-child { border-left: none; }.data-table-header { color: #303133; font-weight: 600; background: #f3f6fa; }.danger { color: #f56c6c; font-weight: 700; }.empty-row { display: block; padding: 20rpx 0; color: #909399; text-align: center; font-size: 23rpx; }
.student-feedback-table { margin-top: 18rpx; border: 1rpx solid #d9dfe7; }.student-table-row { display: grid; grid-template-columns: 1.1fr 3fr; color: #606266; font-size: 23rpx; line-height: 1.7; border-top: 1rpx solid #d9dfe7; }.student-table-row:first-child { border-top: none; }.student-table-row > text { padding: 16rpx; word-break: break-all; }.student-table-row > text:first-child { display: flex; align-items: center; background: #f7f9fb; border-right: 1rpx solid #d9dfe7; }.student-table-header { color: #303133; font-weight: 600; background: #f3f6fa; }.student-table-header > text { padding-top: 12rpx; padding-bottom: 12rpx; }.script-box { margin-top: 12rpx; padding: 20rpx; color: #303133; background: #f4f8fc; border-left: 8rpx solid #1265bd; font-size: 25rpx; line-height: 1.8; word-break: break-all; }
</style>
