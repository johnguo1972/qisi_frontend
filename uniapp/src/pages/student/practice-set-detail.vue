<template>
  <view class="page"><view class="top"><view><text class="title">{{ detail?.title || '精练作业' }}</text><text class="meta">{{ detail?.question_count || questions.length }} 题 · 进度 {{ progress }}%</text></view><view class="actions"><button v-if="detail?.status === 'draft' && !readonly" size="mini" @click="activate">开始练习</button><button v-if="detail?.status === 'active' && !readonly" size="mini" type="primary" @click="submitSet">提交作业</button><button size="mini" @click="exportPdf">导出 PDF</button></view></view>
    <view v-if="!questions.length" class="empty">暂无题目</view>
    <view v-for="(item, index) in questions" :key="item.id" class="question-card">
      <view class="q-head"><text>第 {{ index + 1 }} 题</text><text class="tag">{{ typeLabel(item.display_snapshot?.question_type) }}</text><text class="state">{{ item.latest_attempt?.status ? statusLabel(item.latest_attempt.status) : '未作答' }}</text></view>
      <view class="question-meta">
        <text class="meta-chip">🔖 {{ difficultyLabel(item) }}</text>
        <text v-for="point in knowledgePointLabels(item)" :key="`kp-${item.id}-${point}`" class="meta-chip">💡 {{ point }}</text>
        <text v-for="tag in questionTags(item)" :key="`tag-${item.id}-${tag}`" class="meta-chip">🏷️ {{ tag }}</text>
      </view>
      <text class="stem">{{ plain(item.display_snapshot?.stem || item.display_snapshot?.stem_html) }}</text>
      <view v-if="questionImages(item).length" class="question-images">
        <image
          v-for="image in questionImages(item)"
          :key="image.id || image.file_path || image.url"
          class="question-image"
          :src="questionImageUrl(image)"
          :style="questionImageStyle(image)"
          mode="widthFix"
          lazy-load
          @click="previewQuestionImage(item, image)"
        />
      </view>
      <view v-if="isObjective(item)" class="options"><view v-for="option in (item.display_snapshot?.options || [])" :key="option.label" class="option" :class="{ selected: answers[item.id]?.selected_options?.includes(option.label) }" @click="toggleOption(item, option.label)"><text class="option-label">{{ option.label }}</text><text>{{ plain(option.content) }}</text></view></view>
      <textarea v-else v-model="subjective[item.id]" class="textarea" placeholder="请输入文字答案，或使用拍照上传" />
      <view class="q-actions"><button v-if="!readonly" size="mini" type="primary" :disabled="submitting === item.id" @click="submitOnline(item)">{{ submitting === item.id ? '提交中...' : '提交答案' }}</button><button v-if="!readonly && !isObjective(item)" size="mini" @click="uploadPhoto(item)">拍照上传</button></view>
      <view v-if="item.latest_attempt" class="result-panel" :class="resultClass(item.latest_attempt)">
        <view class="result-title">{{ resultText(item.latest_attempt) }}</view>
        <text class="result-line">我的答案：{{ formatAnswer(item.latest_attempt.student_answer) }}</text>
        <text class="result-line">正确答案：{{ formatAnswer(item.latest_attempt.correct_answer) }}</text>
        <button size="mini" class="analysis-button" @click="toggleAnalysis(item.id)">{{ expandedAnalysis[item.id] ? '收起解析' : '查看解析' }}</button>
        <view v-if="expandedAnalysis[item.id]" class="analysis-content">{{ plain(item.latest_attempt.analysis || '暂无解析') }}</view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { practiceApi } from '@/api/student'
import { getQuestionTypeLabel } from '@/utils/question-type'
import { chooseImage, uploadImage } from '@/utils/image-upload'
import { getApiUrl } from '@/utils/api-config'
import { getPublicMediaUrl } from '@/utils/media-url'

const setId = ref(''); const detail = ref<any>(null); const questions = ref<any[]>([]); const submitting = ref(''); const readonly = ref(false)
const answers = reactive<Record<string, any>>({}); const subjective = reactive<Record<string, string>>({})
const expandedAnalysis = reactive<Record<string, boolean>>({})
const progress = computed(() => Number(detail.value?.progress_percent || 0).toFixed(0))
onLoad((options: any) => { setId.value = String(options?.id || ''); readonly.value = String(options?.readonly || '') === '1' })
onMounted(load)
function plain(value: any) { return String(value || '暂无题干').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim() || '暂无题干' }
function typeLabel(value: string, stem = '', options: any[] = []) { return getQuestionTypeLabel(value, stem, options) }
function statusLabel(value: string) { return ({ pending_review: '待批阅', submitted: '已提交', graded: '已批阅', draft: '草稿' } as Record<string, string>)[value] || value }
function difficultyLabel(item: any) { return item?.display_snapshot?.difficulty_label || item?.display_snapshot?.difficulty || '难度未标注' }
function knowledgePointLabels(item: any) {
  const snapshot = item?.display_snapshot || {}
  if (Array.isArray(snapshot.knowledge_point_labels)) return snapshot.knowledge_point_labels.filter(Boolean)
  const raw = Array.isArray(snapshot.knowledge_points) ? snapshot.knowledge_points : []
  return raw.map((point: any) => typeof point === 'object' ? (point.module || point.name || point.label || point.id) : point).filter(Boolean)
}
function questionTags(item: any) { return Array.isArray(item?.display_snapshot?.tags) ? item.display_snapshot.tags.filter(Boolean) : [] }
function formatAnswer(value: any) {
  if (value && typeof value === 'object') {
    if (Array.isArray(value.selected_options)) return value.selected_options.join('、') || '未作答'
    if (typeof value.selected === 'string') return value.selected || '未作答'
    if (typeof value.text === 'string') return value.text || '未作答'
  }
  const text = String(value || '').trim()
  if (!text) return '暂无'
  return text
    .replace(/\$\\(?:mathrm|text)\{([^{}]*)\}\$/g, '$1')
    .replace(/\\(?:mathrm|text)\{([^{}]*)\}/g, '$1')
}
function resultText(attempt: any) {
  if (attempt?.is_subjective_pending) return '待批阅'
  return attempt?.is_correct ? '回答正确' : '回答错误'
}
function resultClass(attempt: any) {
  if (attempt?.is_subjective_pending) return 'pending'
  return attempt?.is_correct ? 'correct' : 'incorrect'
}
function toggleAnalysis(id: string) { expandedAnalysis[id] = !expandedAnalysis[id] }
function questionImages(item: any) { return Array.isArray(item?.display_snapshot?.images) ? item.display_snapshot.images : [] }
function questionImageUrl(image: any) { return getPublicMediaUrl(image?.url || image?.file_path) }
function questionImageStyle(image: any) {
  const width = Number(image?.display_width)
  return width > 0
    ? { width: `${width}px`, maxWidth: '100%', height: 'auto' }
    : { width: 'auto', maxWidth: '100%', height: 'auto' }
}
function previewQuestionImage(item: any, image: any) {
  const urls = questionImages(item).map(questionImageUrl).filter(Boolean)
  const current = questionImageUrl(image)
  if (urls.length && current) uni.previewImage({ current, urls })
}
function isObjective(item: any) { return ['single_choice', 'multiple_choice', 'true_false'].includes(item.display_snapshot?.question_type) }
function toggleOption(item: any, label: string) { const id = String(item.id); const type = item.display_snapshot?.question_type; const current = answers[id]?.selected_options || []; answers[id] = { selected_options: type === 'single_choice' || type === 'true_false' ? [label] : current.includes(label) ? current.filter((x: string) => x !== label) : [...current, label] } }
async function load() { if (!setId.value) return; const [d, q] = await Promise.all([practiceApi.detail(setId.value), practiceApi.questions(setId.value)]); detail.value = (d as any).data; questions.value = (q as any).data || [] }
async function activate() { const response: any = await practiceApi.activate(setId.value); if (response.code === 0) { detail.value = response.data; uni.showToast({ title: '已开始', icon: 'success' }) } }
async function submitSet() { const response: any = await practiceApi.submitSet(setId.value); if (response.code === 0) { detail.value = response.data; uni.showToast({ title: '作业已提交', icon: 'success' }) } else { uni.showToast({ title: response.message || '请先完成全部题目', icon: 'none' }) } }
async function submitOnline(item: any) { const id = String(item.id); const snapshot = item.display_snapshot || {}; const answer = isObjective(item) ? (answers[id] || { selected_options: [] }) : { text: subjective[id] || '' }; submitting.value = id; try { const response: any = await practiceApi.submit(setId.value, id, { question_id: snapshot.id || item.question_id, answer_content: answer }); if (response.code === 0) { uni.showToast({ title: response.data?.is_pending ? '已提交待批阅' : response.data?.is_correct ? '回答正确' : '回答不正确', icon: 'none' }); await load() } } finally { submitting.value = '' } }
async function uploadPhoto(item: any) { const id = String(item.id); try { const draft: any = await practiceApi.createPhotoDraft(setId.value, id, { question_id: item.question_id }); if (draft.code !== 0) return; const attemptId = draft.data.attempt_id; const files = await chooseImage({ count: 9, sourceType: ['camera', 'album'] }); if (!files.length) return; for (let index = 0; index < files.length; index++) { const file: any = files[index]; const result = await uploadImage({ filePath: file.path, file: file.file, uploadUrl: getApiUrl(`/practice/attempts/${attemptId}/images`), fieldName: 'image', formData: { page_no: index + 1 } } as any); if (result.statusCode < 200 || result.statusCode >= 300 || result.data?.code !== 0) throw new Error(result.data?.message || '图片上传失败'); if (index === files.length - 1) { const submit: any = await practiceApi.submitPhoto(attemptId, {}); if (submit.code !== 0) throw new Error(submit.message || '提交失败') } } uni.showToast({ title: '照片已提交，等待批阅', icon: 'success' }); await load() } catch (error: any) { uni.showToast({ title: error?.message || '照片上传失败', icon: 'none' }) } }
async function exportPdf() { const response: any = await practiceApi.exportPdf(setId.value, { include_answers: false }); if (response.code !== 0) return; const url = getPublicMediaUrl(response.data?.download_url || response.data?.pdf_file_path); if (!url) return; // H5 directly opens; APP/MP downloads to a local file.
  // #ifdef H5
  window.open(url, '_blank')
  // #endif
  // #ifndef H5
  uni.downloadFile({ url, success: result => { if (result.statusCode === 200) uni.openDocument({ filePath: result.tempFilePath, showMenu: true }) } })
  // #endif
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 24rpx; background: #f0f2f5; box-sizing: border-box; }.top { display: flex; justify-content: space-between; align-items: center; gap: 16rpx; margin-bottom: 20rpx; }.title { display: block; color: #303133; font-size: 34rpx; font-weight: 700; }.meta,.state { color: #909399; font-size: 22rpx; }.actions,.q-actions { display: flex; gap: 12rpx; }.question-card { margin-bottom: 20rpx; padding: 24rpx; background: #fff; border-radius: 14rpx; }.q-head { display: flex; align-items: center; gap: 14rpx; margin-bottom: 14rpx; color: #303133; font-size: 26rpx; font-weight: 600; }.tag { padding: 4rpx 10rpx; color: #409eff; background: #ecf5ff; border-radius: 6rpx; font-size: 20rpx; }.state { margin-left: auto; }.stem { display: block; margin-bottom: 18rpx; color: #303133; font-size: 28rpx; line-height: 1.65; }.options { display: flex; flex-direction: column; gap: 12rpx; margin-bottom: 20rpx; }.option { display: flex; gap: 14rpx; padding: 18rpx; border: 1rpx solid #dcdfe6; border-radius: 10rpx; color: #303133; font-size: 25rpx; }.option.selected { border-color: #409eff; background: #ecf5ff; }.option-label { font-weight: 700; }.textarea { width: 100%; min-height: 190rpx; margin-bottom: 18rpx; padding: 16rpx; border: 1rpx solid #dcdfe6; border-radius: 10rpx; box-sizing: border-box; }.empty { padding: 80rpx; color: #909399; text-align: center; }
.question-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8rpx; margin: 0 0 16rpx; }
.meta-chip { padding: 4rpx 10rpx; border-radius: 999rpx; background: #f4f4f5; color: #606266; font-size: 21rpx; }
.result-panel { margin-top: 20rpx; padding: 18rpx; border-radius: 10rpx; }
.result-panel.correct { color: #267a3d; background: #f0f9eb; border: 1rpx solid #b3e19d; }
.result-panel.incorrect { color: #b42318; background: #fef0f0; border: 1rpx solid #fbc4c4; }
.result-panel.pending { color: #8a5a00; background: #fdf6ec; border: 1rpx solid #f5dab1; }
.result-title { margin-bottom: 10rpx; font-size: 28rpx; font-weight: 700; }
.result-line { display: block; margin-top: 6rpx; font-size: 24rpx; line-height: 1.5; }
.analysis-button { display: block; margin: 14rpx 0 0; color: #409eff; background: #fff; border: 1rpx solid #b3d8ff; }
.analysis-content { margin-top: 12rpx; padding: 14rpx; color: #606266; background: #fff; border-radius: 8rpx; font-size: 24rpx; line-height: 1.7; white-space: pre-wrap; }
.question-images { display: flex; flex-direction: column; align-items: flex-start; gap: 16rpx; margin: 4rpx 0 20rpx; }
.question-image { display: block; max-width: 100%; height: auto; border-radius: 8rpx; background: #f7f8fa; }
</style>
