<template>
  <view class="detail-page">

    <!-- 右侧内容区 -->
    <view class="main">
      <!-- #ifndef MP-WEIXIN -->
      <view class="detail-toolbar">
        <button class="back-btn" @click="goBack">返回作业列表</button>
        <text class="toolbar-title">作业详情</text>
      </view>
      <!-- #endif -->
      <!-- 作业信息卡片 -->
      <view v-if="mission" class="mission-card">
        <text class="page-title">{{ isGrading ? '批改作业' : '作业详情' }}</text>
        <text class="mission-name">{{ mission.mission_name }}</text>
        <text class="mission-no">{{ mission.mission_no }}</text>
        <view class="status-badge" :class="mission.status">{{ statusText(mission.status) }}</view>
        <text class="mission-desc">{{ mission.goal_text || '暂无描述' }}</text>
        <view class="meta-grid">
          <view class="meta-item">
            <text class="meta-label">截止时间</text>
            <text class="meta-value">{{ formatDateOnly(mission.end_at, '未设置') }}</text>
          </view>
          <view class="meta-item">
            <text class="meta-label">{{ mission.assignment_mode === 'flat' ? '题目数' : '关卡数' }}</text>
            <text class="meta-value">{{ mission.assignment_mode === 'flat' ? (questions.length || mission.question_count || 0) : (mission.level_count || 0) }}</text>
          </view>
        </view>
      </view>
      <view v-if="mission" class="action-buttons">
        <button v-if="mission.status === 'draft'" @click="publishMission" class="action-btn publish">
          发布作业
        </button>
        <button @click="cloneMission" class="action-btn clone">克隆作业</button>
        <button @click="exportPdf" class="action-btn export">导出PDF</button>
        <button @click="showQrcode" class="action-btn qrcode">作业二维码</button>
      </view>
      <view v-if="qrcodeInfo" class="qrcode-panel">
        <image v-if="qrcodeInfo.image_data" class="qrcode-image" :src="qrcodeInfo.image_data" mode="widthFix" />
        <text>作业码：{{ qrcodeInfo.short_code }}</text>
        <text class="qrcode-url">{{ qrcodeInfo.url }}</text>
        <view class="qrcode-actions">
          <button size="mini" @click="copyQrcodeUrl">复制二维码链接</button>
          <button size="mini" class="save-qrcode-btn" @click="saveQrcodeImage">保存二维码图片</button>
        </view>
      </view>
      <view v-if="isGrading" class="grading-panel">
        <view class="panel-header"><text class="panel-title">学生提交与批改</text></view>
        <view v-if="gradingLoading" class="empty">加载提交记录中...</view>
        <view v-else-if="gradingAttempts.length === 0" class="empty">暂无学生提交</view>
        <view v-for="attempt in gradingAttempts" :key="attempt.id" class="grading-item">
          <view class="grading-question">
            <text class="grading-student">{{ studentName(attempt.student_id) }}</text>
            <text>{{ attempt.question_no || attempt.question_id }}</text>
            <text class="grading-type">{{ questionTypeText(attempt.question_type) }}</text>
            <text class="grading-stem">{{ plainText(attempt.stem) }}</text>
            <view v-if="attempt.options?.length" class="grading-options">
              <text v-for="option in attempt.options" :key="option.label" class="grading-option">
                {{ option.label }}. {{ plainText(option.content) }}
              </text>
            </view>
          </view>
          <view class="grading-answer answer-row">
            <text class="answer-label">学生答案</text>
            <text class="answer-value">{{ answerText(attempt.answer_content, attempt.options) }}</text>
          </view>
          <view class="grading-answer correct-answer answer-row">
            <text class="answer-label">正确答案</text>
            <text class="answer-value">{{ correctAnswerText(attempt.correct_answer, attempt.options) }}</text>
          </view>
          <view class="grading-controls">
            <input class="score-input" type="number" v-model.number="attempt.score" placeholder="分数" />
            <input class="feedback-input" v-model="attempt.feedback" placeholder="批语（可选）" />
            <button class="save-grade-btn" @click="saveGrade(attempt)">保存批改</button>
            <button class="variant-btn" @click="generateVariant(attempt)">生成同类题</button>
          </view>
        </view>
      </view>
      <!-- 新作业使用平铺题目，不再展示关卡设置 -->
      <view v-if="!isGrading && mission?.assignment_mode === 'flat'" class="levels-panel flat-questions-panel">
        <view class="panel-header"><text class="panel-title">题目列表（{{ questions.length }}题）</text></view>
        <view v-for="(question, index) in questions" :key="question.id" class="flat-question-row">
          <text class="flat-question-no">{{ index + 1 }}</text>
          <text class="flat-question-stem">{{ question.stem_preview || question.stem || '暂无题干' }}</text>
        </view>
        <view v-if="questions.length === 0" class="empty">暂无题目</view>
      </view>
      <!-- 历史作业继续展示关卡 -->
      <view v-if="!isGrading && mission?.assignment_mode !== 'flat'" class="levels-panel">
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
import { formatDateOnly } from '@/utils/display-format'

const mission = ref<Mission | null>(null)
const levels = ref<any[]>([])
const questions = ref<any[]>([])
const missionId = ref<string>('')
const isGrading = ref(false)
const gradingLoading = ref(false)
const gradingAttempts = ref<any[]>([])
const gradingStudents = ref<any[]>([])
const qrcodeInfo = ref<any>(null)

onLoad((options: any) => {
  const id = String(options?.id || '')
  isGrading.value = options?.mode === 'grading'
  if (!id) {
    uni.showToast({ title: '缺少作业ID', icon: 'none' })
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
    if (res.data?.assignment_mode === 'flat') {
      const questionRes: any = await missionApi.questions(missionId.value)
      questions.value = Array.isArray(questionRes.data) ? questionRes.data : []
    }
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
function plainText(value: any): string {
  return String(value ?? '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .trim()
}

function optionLabel(value: any, options: any[] = []): string {
  const label = String(value ?? '').trim()
  const option = options.find(item => String(item?.label ?? '').trim().toUpperCase() === label.toUpperCase())
  return option ? `${option.label}. ${plainText(option.content)}` : label
}

function choiceText(value: any, options: any[] = []): string {
  const values = Array.isArray(value) ? value : [value]
  return values
    .map(item => optionLabel(item, options))
    .filter(Boolean)
    .join('、') || '未作答'
}

function answerText(value: any, options: any[] = []): string {
  if (value === null || value === undefined || value === '') return '未作答'
  if (typeof value === 'string') {
    const text = value.trim()
    if (!text) return '未作答'
    if (text.startsWith('{') || text.startsWith('[')) {
      try { return answerText(JSON.parse(text), options) } catch { /* keep legacy text */ }
    }
    return text
  }
  if (typeof value !== 'object') return String(value)
  if (Array.isArray(value)) return choiceText(value, options)
  if (Array.isArray(value.selected_options)) return choiceText(value.selected_options, options)
  if (value.selected !== undefined && value.selected !== '') {
    const selected = String(value.selected).trim().toLowerCase()
    if (selected === 'true') return '正确'
    if (selected === 'false') return '错误'
    return optionLabel(value.selected, options)
  }
  for (const key of ['text', 'answer', 'content']) {
    if (value[key] !== undefined && String(value[key]).trim()) return String(value[key]).trim()
  }
  if (Array.isArray(value.images) && value.images.length) return `已上传 ${value.images.length} 张图片答案`
  return '未作答'
}

function correctAnswerText(value: any, options: any[] = []): string {
  if (value === null || value === undefined || value === '') return '暂无参考答案'
  if (typeof value === 'object') return answerText(value, options)
  const raw = String(value).trim()
  if (!raw) return '暂无参考答案'
  if (options.length && /^[A-Za-z]+(?:[,，、;；|\s]+[A-Za-z]+)*$/.test(raw)) {
    const values = raw.toUpperCase().split(/[,，、;；|\s]+/).filter(Boolean)
    return choiceText(values.length > 1 ? values : raw.toUpperCase().split(''), options)
  }
  return raw
}

function questionTypeText(type: string): string {
  const map: Record<string, string> = {
    single_choice: '单选题', multiple_choice: '多选题', true_false: '判断题',
    fill_blank: '填空题', short_answer: '简答题', essay: '论述题',
    computation: '计算题', calculation: '计算题', proof: '证明题',
  }
  return map[String(type || '').trim().toLowerCase()] || ''
}
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
    block_a: 'A模式分块', allow_a: '允许A模式', require_guidance: '需引导', free_practice: '自由练习'
  }
  return map[mode] || mode
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.redirectTo({ url: '/pages/teacher/layout?section=assignment-list' })
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

async function cloneMission() {
  try {
    const res: any = await missionApi.clone(missionId.value)
    uni.showToast({ title: '克隆成功', icon: 'success' })
    uni.navigateBack({
      delta: 1,
      success: () => {
        setTimeout(() => uni.$emit('mission-list-refresh', { id: res.data?.id }), 0)
      },
    })
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

async function showQrcode() {
  try {
    const res: any = await missionApi.qrcodeInfo(missionId.value)
    qrcodeInfo.value = res.data
  } catch { uni.showToast({ title: '获取二维码失败', icon: 'none' }) }
}

function copyQrcodeUrl() {
  if (!qrcodeInfo.value?.url) return
  uni.setClipboardData({ data: qrcodeInfo.value.url, success: () => uni.showToast({ title: '链接已复制', icon: 'success' }) })
}

function saveQrcodeImage() {
  const imageData = String(qrcodeInfo.value?.image_data || '')
  if (!imageData.startsWith('data:image/')) {
    uni.showToast({ title: '二维码图片未准备好', icon: 'none' })
    return
  }

  // #ifdef H5
  const link = document.createElement('a')
  link.href = imageData
  link.download = `作业二维码-${qrcodeInfo.value?.short_code || 'qrcode'}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  uni.showToast({ title: '二维码已保存', icon: 'success' })
  // #endif

  // #ifdef MP-WEIXIN
  const base64 = imageData.split(',')[1]
  const filePath = `${(globalThis as any).wx?.env?.USER_DATA_PATH || ''}/qrcode-${Date.now()}.png`
  const fileManager = (uni as any).getFileSystemManager?.()
  if (!fileManager || !filePath.startsWith('wxfile://')) {
    uni.showToast({ title: '当前环境不支持保存图片', icon: 'none' })
    return
  }
  fileManager.writeFile({
    filePath,
    data: base64,
    encoding: 'base64',
    success: () => uni.saveImageToPhotosAlbum({
      filePath,
      success: () => uni.showToast({ title: '二维码已保存到相册', icon: 'success' }),
      fail: () => uni.showToast({ title: '保存失败，请授权相册权限', icon: 'none' }),
    }),
    fail: () => uni.showToast({ title: '二维码文件生成失败', icon: 'none' }),
  })
  // #endif
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
.detail-toolbar { display: flex; align-items: center; gap: 16px; margin-bottom: 18px; }
.back-btn { margin: 0; padding: 8px 16px; color: #606266; background: #fff; border: 1px solid #dcdfe6; border-radius: 6px; font-size: 13px; }
.back-btn::after { border: none; }
.toolbar-title { color: #303133; font-size: 18px; font-weight: 600; }
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
.grading-type { color: #409eff; background: #ecf5ff; padding: 3rpx 10rpx; border-radius: 4rpx; font-size: 20rpx; }
.grading-stem { width: 100%; color: #333; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }
.grading-options { width: 100%; display: flex; flex-direction: column; gap: 6rpx; padding: 8rpx 0 2rpx 24rpx; box-sizing: border-box; }
.grading-option { color: #606266; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.5; }
.grading-answer { display: flex; gap: 12rpx; margin: 14rpx 0; white-space: normal; overflow-wrap: anywhere; }
.answer-label { flex: 0 0 auto; color: #606266; font-weight: 600; }
.answer-value { color: #303133; white-space: pre-wrap; overflow-wrap: anywhere; }
.correct-answer { padding: 10rpx 14rpx; background: #f0f9eb; border-radius: 6rpx; }
.correct-answer .answer-label { color: #67c23a; }
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
.flat-questions-panel { padding-bottom: 16px; }
.flat-question-row { display: flex; gap: 12px; align-items: flex-start; padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.flat-question-no { width: 28px; color: #409eff; font-weight: 600; }
.flat-question-stem { flex: 1; color: #303133; line-height: 1.5; }
.qrcode { background: #8e44ad; }
.qrcode-panel { display: flex; flex-direction: column; align-items: center; gap: 14rpx; background: #fff; border-radius: 12rpx; padding: 24rpx; margin-bottom: 20rpx; }
.qrcode-image { width: 360rpx; max-width: 100%; }
.qrcode-url { color: #666; font-size: 22rpx; word-break: break-all; }
.qrcode-actions { display: flex; align-items: center; justify-content: center; gap: 16rpx; flex-wrap: wrap; }
.save-qrcode-btn { color: #67c23a; border-color: #b3e19d; background: #f0f9eb; }
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
