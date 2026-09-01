<template>
  <view class="wrongbook">
    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">错题本</text>
      </view>
      <!-- 统计卡片 -->
      <view class="stats-row">
        <view class="stat-item">
          <text class="stat-value">{{ items.length }}</text>
          <text class="stat-label">总错题数</text>
        </view>
        <view class="stat-item">
          <text class="stat-value">{{ statusCount('not_reviewed') }}</text>
          <text class="stat-label">未复盘</text>
        </view>
        <view class="stat-item">
          <text class="stat-value">{{ statusCount('mastered') }}</text>
          <text class="stat-label">已掌握</text>
        </view>
      </view>
      <view class="filter-panel">
        <view class="filter-item">
          <text class="filter-label">科目</text>
          <picker :range="subjectRange" :value="subjectIndex" @change="onSubjectChange">
            <view class="filter-picker">{{ selectedSubjectLabel }}</view>
          </picker>
        </view>
        <view class="filter-item">
          <text class="filter-label">班级</text>
          <picker :range="classRange" :value="classIndex" @change="onClassChange">
            <view class="filter-picker">{{ selectedClassLabel }}</view>
          </picker>
        </view>
      </view>
      <!-- 错题列表 -->
      <view class="list-panel">
        <view class="panel-header">
          <text class="panel-title">错题列表</text>
        </view>
        <view class="wrong-list">
          <view v-for="item in items" :key="item.id" class="wrong-card"
                @click="goDetail(item)">
            <!-- #ifdef MP-WEIXIN -->
            <view class="wrong-header mp-wrong-header">
              <view class="mp-wrong-meta">
                <view class="mp-wrong-meta-left">
                  <text class="q-no">{{ item.question_no || '题目' + item.question_id }}</text>
                  <view class="question-type">{{ typeLabel(item.question_type) }}</view>
                </view>
                <view class="status-tag" :class="item.status">{{ displayStatus(item.status) }}</view>
              </view>
              <text class="question-stem">{{ plainStem(item) }}</text>
            </view>
            <!-- #endif -->
            <!-- #ifndef MP-WEIXIN -->
            <view class="wrong-header">
              <text class="q-no">{{ item.question_no || '题目' + item.question_id }}</text>
              <view class="question-summary">
                <view class="question-type">{{ typeLabel(item.question_type) }}</view>
                <view class="question-stem" v-html="renderedStem(item)"></view>
              </view>
              <view class="status-tag" :class="item.status">{{ statusText(item.status) }}</view>
            </view>
            <!-- #endif -->
            <view class="wrong-question">
              <image
                v-if="item.images?.length"
                :src="questionImageUrl(item.images[0])"
                class="question-image"
                mode="widthFix"
              />
            </view>
            <view class="wrong-footer">
              <text class="retry-count">重做 {{ item.retry_count }} 次</text>
              <view class="question-meta">
                <text class="meta-chip">📚 {{ item.subject_label || '未设置科目' }}</text>
                <text class="meta-chip">🔖 {{ item.difficulty_label || '难度未标注' }}</text>
                <text v-for="point in (item.knowledge_point_labels || [])" :key="`kp-${item.id}-${point}`" class="meta-chip">💡 {{ point }}</text>
                <text v-for="tag in (item.tags || [])" :key="`tag-${item.id}-${tag}`" class="meta-chip">🏷️ {{ tag }}</text>
              </view>
              <view class="footer-actions"><button class="btn-variants" @click.stop="goVariants(item.id)">练同类题</button><button class="btn-practice" @click.stop="goPractice(item.id)">加入精练</button></view>
            </view>
          </view>
          <view v-if="items.length === 0" class="empty">
            <text>太棒了！还没有错题记录 🎉</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { wrongbookApi } from '@/api/student.ts'
import { studentClassApi } from '@/api/index.ts'
import { renderWithKatex } from '@/utils/katex-renderer'
import { getMediaUrl } from '@/utils/media-url'
import { STUDENT_SUBJECT_OPTIONS } from '@/constants/student-filters'

const items = ref<any[]>([])
const renderedStemMap = ref<Record<string, string>>({})

// 与教师题库使用相同的 canonical subject code 和中文名称。
const selectedSubject = ref('')
const classOptions = ref<Array<{ id: string; name: string }>>([{ id: '', name: '全部班级' }])
const selectedClassId = ref('')
const subjectOptions = ref([STUDENT_SUBJECT_OPTIONS[0]])
const subjectRange = computed(() => subjectOptions.value.map(item => item.name))
const classRange = computed(() => classOptions.value.map(item => item.name))
const subjectIndex = computed(() => Math.max(0, subjectOptions.value.findIndex(item => item.code === selectedSubject.value)))
const classIndex = computed(() => Math.max(0, classOptions.value.findIndex(item => item.id === selectedClassId.value)))
const selectedSubjectLabel = computed(() => subjectOptions.value.find(item => item.code === selectedSubject.value)?.name || '全部科目')
const selectedClassLabel = computed(() => classOptions.value.find(item => item.id === selectedClassId.value)?.name || '全部班级')

onMounted(async () => {
  await loadClasses()
  await loadItems()
})

async function loadClasses() {
  try {
    const res: any = await studentClassApi.myClasses()
    const rawClasses = res.data?.items || res.data || []
    const classes = rawClasses.map((item: any) => ({
      id: String(item.class_id || item.id),
      name: item.class_name || item.name || '未命名班级',
    }))
    classOptions.value = [{ id: '', name: '全部班级' }, ...classes]
    const subjectCodes = Array.isArray(res.data?.subjects)
      ? res.data.subjects
      : rawClasses.flatMap((item: any) => item.teacher_subjects || (item.subject ? [item.subject] : []))
    const allowed = new Set(subjectCodes.map((value: unknown) => String(value || '').trim().toLowerCase()))
    const matched = STUDENT_SUBJECT_OPTIONS.filter(item => item.code && allowed.has(item.code))
    subjectOptions.value = [STUDENT_SUBJECT_OPTIONS[0], ...matched]
  } catch (e) {
    console.error('加载班级筛选项失败:', e)
    subjectOptions.value = [STUDENT_SUBJECT_OPTIONS[0]]
  }
}

async function loadItems() {
  try {
    const res = await wrongbookApi.list({
      subject: selectedSubject.value || undefined,
      class_id: selectedClassId.value || undefined,
    })
    const source = res.data || []
    const seen = new Set<string>()
    items.value = source.filter((item: any) => {
      const questionId = String(item.question_id || item.id)
      if (seen.has(questionId)) return false
      seen.add(questionId)
      return true
    })
    await renderStems()
    if (items.value.length === 0) {
      console.log('错题本为空，可能原因：1) 答错的题为主观题（不会自动进错题本） 2) 答对的题不会进入错题本 3) 数据还未落库')
    }
  } catch (e) {
    console.error('Failed to load wrong book:', e)
    uni.showToast({ title: '加载错题本失败', icon: 'none', duration: 3000 })
  }
}

function onSubjectChange(event: any) {
  selectedSubject.value = subjectOptions.value[Number(event?.detail?.value || 0)]?.code || ''
  loadItems()
}

function onClassChange(event: any) {
  selectedClassId.value = classOptions.value[Number(event?.detail?.value || 0)]?.id || ''
  loadItems()
}

async function renderStems() {
  const rendered: Record<string, string> = {}
  for (const item of items.value) {
    rendered[item.id] = await renderWithKatex(item.stem_html || item.stem || '')
  }
  renderedStemMap.value = rendered
}

function renderedStem(item: any): string {
  return renderedStemMap.value[item.id] || item.stem_html || item.stem || '\u6682\u65e0\u9898\u5e72\u5185\u5bb9'
}

// MP-WEIXIN 使用原生 text 展示题干，避免 v-html/rich-text 在不同基础库中丢失节点。
function plainStem(item: any): string {
  const raw = String(item?.stem || item?.stem_html || '').trim()
  if (!raw) return '暂无题干内容'
  return raw
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .trim() || '暂无题干内容'
}

function questionImageUrl(image: any): string {
  return getMediaUrl(image?.url || image?.file_path || '')
}

function typeLabel(type: string): string {
  const labels: Record<string, string> = {
    single_choice: '\u5355\u9009\u9898',
    multiple_choice: '\u591a\u9009\u9898',
    fill_blank: '\u586b\u7a7a\u9898',
    short_answer: '\u7b80\u7b54\u9898',
    essay: '\u8bba\u8ff0\u9898',
    true_false: '\u5224\u65ad\u9898',
    computation: '\u8ba1\u7b97\u9898',
    calculation: '\u8ba1\u7b97\u9898',
    proof: '\u8bc1\u660e\u9898',
    unknown: '\u672a\u8bc6\u522b',
  }
  return labels[String(type || '').trim().toLowerCase()] || '\u672a\u8bc6\u522b'
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    not_reviewed: '未复盘', reviewing: '复习中', consolidating: '巩固中', mastered: '已掌握',
  }
  return map[status] || status
}

function displayStatus(status: unknown): string {
  const value = String(status || '').trim().toLowerCase()
  const labels: Record<string, string> = {
    not_reviewed: '未复盘',
    reviewing: '复习中',
    consolidating: '巩固中',
    mastered: '已掌握',
  }
  return labels[value] || '未复盘'
}

function statusCount(status: string): number {
  return items.value.filter(i => i.status === status).length
}

function goDetail(item: any) {
  uni.navigateTo({ url: `/pages/student/guidance?questionId=${item.question_id}` })
}

async function goVariants(id: number) {
  try {
    const res = await wrongbookApi.variants(id)
    const variants = res.data || []
    if (variants.length === 0) {
      uni.showToast({ title: '暂无同类题', icon: 'none' })
      return
    }
    uni.navigateTo({ url: `/pages/student/wrongbook-variants?id=${id}` })
  } catch (e: any) {
    console.error('获取同类题失败:', e)
    uni.showToast({ title: '获取失败，请重试', icon: 'none' })
  }
}

function goPractice(id: string) {
  uni.navigateTo({ url: `/pages/student/wrongbook-practice-candidates?id=${id}` })
}
</script>

<style scoped>
.wrongbook {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 0;
  flex: 1;
  padding: 30rpx 40rpx;
}
.page-header {
  margin-bottom: 24rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.stats-row {
  display: flex;
  gap: 20rpx;
  margin-bottom: 30rpx;
}
.stat-item {
  flex: 1;
  text-align: center;
  padding: 24rpx;
  background: #fff;
  border-radius: 12rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.stat-value {
  font-size: 40rpx;
  font-weight: bold;
  color: #409eff;
  display: block;
}
.stat-label {
  font-size: 22rpx;
  color: #999;
  display: block;
  margin-top: 6rpx;
}
.filter-panel {
  display: flex;
  gap: 20rpx;
  margin-bottom: 24rpx;
  padding: 20rpx 24rpx;
  background: #fff;
  border-radius: 12rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.filter-item {
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-width: 240rpx;
}
.filter-label {
  flex-shrink: 0;
  color: #606266;
  font-size: 24rpx;
}
.filter-item picker {
  flex: 1;
  min-width: 0;
}
.filter-picker {
  min-width: 160rpx;
  padding: 10rpx 16rpx;
  border: 1rpx solid #dcdfe6;
  border-radius: 8rpx;
  color: #303133;
  font-size: 24rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.panel-header {
  margin-bottom: 24rpx;
}
.panel-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}
.wrong-list {
  display: flex;
  flex-direction: column;
}
.wrong-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 16rpx;
  cursor: pointer;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  transition: box-shadow 0.2s;
}
.wrong-card:hover {
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);
}
.wrong-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.q-no {
  flex: 0 0 auto;
  white-space: nowrap;
  padding-top: 5rpx;
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
}
.wrong-question {
  margin: 0 0 18rpx;
}
.question-summary {
  display: flex;
  align-items: flex-start;
  gap: 10rpx;
  flex: 1;
  min-width: 0;
  margin: 0 16rpx;
}
.question-type {
  flex: 0 0 auto;
  display: inline-block;
  margin-bottom: 0;
  padding: 3rpx 10rpx;
  border-radius: 4rpx;
  color: #409eff;
  background: #ecf5ff;
  font-size: 20rpx;
}
.question-stem {
  color: #333;
  font-size: 25rpx;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.question-stem :deep(.katex) {
  font-size: 1em;
}
.question-stem :deep(.katex-display) {
  margin: 8rpx 0;
  overflow-x: auto;
}
.question-image {
  display: block;
  max-width: 100%;
  max-height: 260rpx;
  margin-top: 12rpx;
  border-radius: 6rpx;
}
.status-tag {
  font-size: 22rpx;
  padding: 4rpx 16rpx;
  border-radius: 4rpx;
}
.status-tag.not_reviewed { background: #fff3e0; color: #ff9800; }
.status-tag.reviewing { background: #e3f2fd; color: #2196f3; }
.status-tag.consolidating { background: #f3e5f5; color: #9c27b0; }
.status-tag.mastered { background: #e8f5e9; color: #4caf50; }
.wrong-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12rpx;
}
.question-meta { display: flex; flex: 1; min-width: 260rpx; flex-wrap: wrap; align-items: center; gap: 8rpx; }
.meta-chip { padding: 4rpx 10rpx; border-radius: 999rpx; background: #f4f4f5; color: #606266; font-size: 21rpx; }
.footer-actions { display: flex; gap: 10rpx; }
.retry-count {
  font-size: 22rpx;
  color: #999;
}
.btn-variants {
  font-size: 22rpx;
  padding: 6rpx 24rpx;
  background: linear-gradient(135deg, #ff9800, #f57c00);
  color: #fff;
  border: none;
  border-radius: 8rpx;
  line-height: 1.4;
  margin: 0;
  height: auto;
  min-width: 0;
}
.btn-variants:active {
  opacity: 0.85;
}
.empty {
  text-align: center;
  padding: 100rpx;
  color: #999;
  font-size: 26rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .wrongbook {
    flex-direction: column;
  }
  .main {
    margin-left: 0;
    width: 100%;
  }
  .stats-row {
    flex-wrap: wrap;
  }
  .stat-item {
    min-width: calc(33% - 14rpx);
  }
  .filter-panel {
    flex-direction: column;
    gap: 12rpx;
  }
  .filter-item {
    width: 100%;
    min-width: 0;
  }
}
.btn-practice { margin: 0; padding: 6rpx 20rpx; color: #fff; background: #67c23a; border-radius: 8rpx; font-size: 22rpx; line-height: 1.4; }

/* #ifdef MP-WEIXIN */
.wrongbook,
.wrongbook .main {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
.wrongbook .main {
  padding: 20rpx;
}
.wrongbook .stats-row {
  flex-wrap: wrap;
  gap: 12rpx;
}
.wrongbook .stat-item {
  flex: 0 0 calc((100% - 24rpx) / 3);
  min-width: 0;
  box-sizing: border-box;
  padding: 16rpx 4rpx;
}
.wrongbook .stat-value {
  font-size: 34rpx;
}
.wrongbook .stat-label {
  font-size: 19rpx;
  white-space: nowrap;
}
.wrongbook .list-panel,
.wrongbook .wrong-card {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
.wrongbook .question-summary,
.wrongbook .question-stem {
  min-width: 0;
  overflow: hidden;
}
.wrongbook .mp-wrong-header {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  width: 100%;
}
.wrongbook .mp-wrong-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 0;
  margin-bottom: 10rpx;
}
.wrongbook .mp-wrong-meta-left {
  display: flex;
  align-items: center;
  min-width: 0;
}
.wrongbook .mp-wrong-meta .q-no {
  flex: 0 0 auto;
  width: 36rpx;
  padding-top: 0;
  text-align: left;
}
.wrongbook .mp-wrong-meta .question-type {
  flex: 0 0 auto;
  padding: 3rpx 6rpx;
  text-align: center;
  white-space: nowrap;
}
.wrongbook .mp-wrong-header .question-stem {
  display: block;
  width: 100%;
  margin: 0;
  line-height: 1.65;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-all;
}
.wrongbook .mp-wrong-meta .status-tag {
  flex: 0 0 auto;
  padding: 4rpx 8rpx;
  white-space: nowrap;
}
.wrongbook .wrong-question .question-image {
  display: block;
  width: 100%;
  max-width: 100%;
  height: auto;
  max-height: 420rpx;
  margin: 12rpx 0 0;
  object-fit: contain;
}
/* #endif */
</style>
