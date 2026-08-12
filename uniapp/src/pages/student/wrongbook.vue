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
              <button class="btn-variants" @click.stop="goVariants(item.id)">练同类题</button>
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
import { ref, onMounted } from 'vue'
import { wrongbookApi } from '@/api/student.ts'
import { renderWithKatex } from '@/utils/katex-renderer'
import { getMediaUrl } from '@/utils/media-url'

const items = ref<any[]>([])
const renderedStemMap = ref<Record<string, string>>({})

onMounted(async () => {
  try {
    const res = await wrongbookApi.list()
    items.value = res.data || []
    await renderStems()
    if (items.value.length === 0) {
      console.log('错题本为空，可能原因：1) 答错的题为主观题（不会自动进错题本） 2) 答对的题不会进入错题本 3) 数据还未落库')
    }
  } catch (e) {
    console.error('Failed to load wrong book:', e)
    uni.showToast({ title: '加载错题本失败', icon: 'none', duration: 3000 })
  }
})

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
  justify-content: space-between;
}
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
}

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
