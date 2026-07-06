<template>
  <view class="variants-page">
    <!-- 导航栏 -->
    <view class="nav-bar">
      <view class="nav-left" @click="goBack">
        <text class="back-icon">&#8592;</text>
        <text class="back-text">返回</text>
      </view>
      <text class="nav-title">同类题练习</text>
      <view class="nav-right">
        <button
          class="btn-export"
          @click="exportPDF"
          :disabled="!variants.length"
        >
          导出PDF
        </button>
      </view>
    </view>

    <!-- 加载中 -->
    <view v-if="loading" class="loading">
      <text class="loading-text">加载中...</text>
    </view>

    <!-- 空状态 -->
    <view v-else-if="!variants.length" class="empty">
      <text class="empty-icon">📭</text>
      <text class="empty-text">暂无同类题</text>
      <text class="empty-hint">系统会根据错题知识点推荐相似题目</text>
    </view>

    <!-- 题目列表 -->
    <view v-else class="variant-list">
      <view v-for="item in variants" :key="item.id" class="variant-card">
        <view class="card-header">
          <view class="card-tags">
            <view class="tag type-tag">{{ typeLabel(item.question_type) }}</view>
            <view class="tag diff-tag" :class="diffClass(item.difficulty)">
              {{ diffLabel(item.difficulty) }}
            </view>
          </view>
          <text class="card-no">{{ item.question_no || '#' + item.id }}</text>
        </view>

        <view class="card-body">
          <text class="stem-text">{{ truncate(item.stem || '', 120) }}</text>
          <!-- 有图片时显示 -->
          <image
            v-if="item.stem_image"
            :src="item.stem_image"
            class="stem-image"
            mode="aspectFit"
          />
        </view>

        <view class="card-footer">
          <view class="knowledge-tags" v-if="item.knowledge_points?.length">
            <text
              v-for="kp in item.knowledge_points"
              :key="kp"
              class="kp-tag"
            >{{ kp }}</text>
          </view>
          <button class="btn-practice" @click="startPractice(item.id)">
            开始练习
          </button>
        </view>
      </view>

      <!-- 底部操作 -->
      <view class="bottom-actions">
        <button class="btn-back-full" @click="goBack">
          返回错题本
        </button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { wrongbookApi } from '@/api/student.ts'

interface VariantItem {
  id: number
  question_no?: string
  question_type: string
  difficulty: number
  stem?: string
  stem_image?: string
  knowledge_points?: string[]
}

const wrongId = ref(0)
const variants = ref<VariantItem[]>([])
const loading = ref(true)

onMounted(async () => {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as any
  wrongId.value = parseInt(page.options.id || '0')

  if (!wrongId.value) {
    uni.showToast({ title: '缺少错题ID', icon: 'none' })
    loading.value = false
    return
  }

  await loadVariants()
})

async function loadVariants() {
  loading.value = true
  try {
    const res = await wrongbookApi.variants(wrongId.value)
    variants.value = res.data || []
  } catch (e: any) {
    console.error('获取同类题失败:', e)
    uni.showToast({ title: '加载失败，请重试', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function startPractice(questionId: number) {
  uni.navigateTo({
    url: `/pages/student/guidance?questionId=${questionId}`,
  })
}

function exportPDF() {
  if (!variants.value.length) {
    uni.showToast({ title: '暂无可导出的题目', icon: 'none' })
    return
  }
  const ids = variants.value.map(v => v.id).join(',')
  uni.navigateTo({
    url: `/pages/student/export?ids=${ids}&title=同类题练习`,
  })
}

function goBack() {
  uni.navigateBack()
}

function typeLabel(type: string): string {
  const map: Record<string, string> = {
    single_choice: '单选',
    multiple_choice: '多选',
    fill_blank: '填空',
    short_answer: '简答',
    essay: '论述',
    true_false: '判断',
    computation: '计算',
    proof: '证明',
  }
  return map[type] || type
}

function diffClass(difficulty: number): string {
  if (difficulty <= 2) return 'diff-easy'
  if (difficulty <= 4) return 'diff-medium'
  return 'diff-hard'
}

function diffLabel(difficulty: number): string {
  if (difficulty <= 2) return '简单'
  if (difficulty <= 4) return '中等'
  return '困难'
}

function truncate(str: string, len: number): string {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}
</script>

<style scoped>
.variants-page {
  min-height: 100vh;
  background: #f0f2f5;
}

/* 导航栏 */
.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 40rpx;
  background: #fff;
  border-bottom: 1rpx solid #e8e8e8;
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-left {
  display: flex;
  align-items: center;
  gap: 8rpx;
  cursor: pointer;
}
.back-icon {
  font-size: 32rpx;
  color: #409eff;
}
.back-text {
  font-size: 26rpx;
  color: #409eff;
}
.nav-title {
  font-size: 30rpx;
  font-weight: bold;
  color: #333;
}
.btn-export {
  font-size: 24rpx;
  padding: 8rpx 24rpx;
  background: linear-gradient(135deg, #409eff, #3a8ee6);
  color: #fff;
  border: none;
  border-radius: 8rpx;
  line-height: 1.4;
  margin: 0;
  height: auto;
  min-width: 0;
}
.btn-export[disabled] {
  background: #ccc;
}
.btn-export:active {
  opacity: 0.85;
}

/* 加载中 */
.loading {
  display: flex;
  justify-content: center;
  padding: 200rpx 0;
}
.loading-text {
  font-size: 28rpx;
  color: #999;
}

/* 空状态 */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 200rpx 0;
}
.empty-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}
.empty-text {
  font-size: 28rpx;
  color: #666;
  margin-bottom: 12rpx;
}
.empty-hint {
  font-size: 24rpx;
  color: #999;
}

/* 题目列表 */
.variant-list {
  padding: 30rpx 40rpx;
}

.variant-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  transition: box-shadow 0.2s;
}
.variant-card:hover {
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.card-tags {
  display: flex;
  gap: 12rpx;
}
.tag {
  font-size: 20rpx;
  padding: 4rpx 16rpx;
  border-radius: 4rpx;
}
.type-tag {
  background: #e3f2fd;
  color: #2196f3;
}
.diff-tag {
  background: #e8f5e9;
  color: #4caf50;
}
.diff-easy {
  background: #e8f5e9;
  color: #4caf50;
}
.diff-medium {
  background: #fff3e0;
  color: #ff9800;
}
.diff-hard {
  background: #ffebee;
  color: #f44336;
}
.card-no {
  font-size: 24rpx;
  color: #999;
}

.card-body {
  margin-bottom: 16rpx;
}
.stem-text {
  font-size: 26rpx;
  color: #333;
  line-height: 1.6;
  display: block;
}
.stem-image {
  width: 100%;
  max-height: 400rpx;
  margin-top: 16rpx;
  border-radius: 8rpx;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.knowledge-tags {
  display: flex;
  gap: 8rpx;
  flex-wrap: wrap;
  flex: 1;
  margin-right: 16rpx;
}
.kp-tag {
  font-size: 20rpx;
  padding: 4rpx 12rpx;
  background: #f5f5f5;
  color: #666;
  border-radius: 4rpx;
}
.btn-practice {
  font-size: 24rpx;
  padding: 10rpx 32rpx;
  background: linear-gradient(135deg, #409eff, #3a8ee6);
  color: #fff;
  border: none;
  border-radius: 8rpx;
  line-height: 1.4;
  margin: 0;
  height: auto;
  min-width: 0;
}
.btn-practice:active {
  opacity: 0.85;
}

/* 底部操作 */
.bottom-actions {
  margin-top: 30rpx;
  padding-bottom: 40rpx;
}
.btn-back-full {
  width: 100%;
  font-size: 28rpx;
  padding: 20rpx 0;
  background: #fff;
  color: #409eff;
  border: 1rpx solid #409eff;
  border-radius: 8rpx;
}
.btn-back-full:active {
  background: #ecf5ff;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .nav-bar {
    padding: 20rpx 24rpx;
  }
  .variant-list {
    padding: 24rpx;
  }
  .card-footer {
    flex-direction: column;
    gap: 16rpx;
    align-items: flex-start;
  }
  .btn-practice {
    width: 100%;
    text-align: center;
  }
  .knowledge-tags {
    margin-right: 0;
  }
}
</style>
