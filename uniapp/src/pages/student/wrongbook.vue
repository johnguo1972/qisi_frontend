<template>
  <view class="wrongbook">
    <StudentSidebar activeItem="wrongbook" />
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
            <view class="wrong-header">
              <text class="q-no">{{ item.question_no || '题目' + item.question_id }}</text>
              <view class="status-tag" :class="item.status">{{ statusText(item.status) }}</view>
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
import StudentSidebar from '@/components/StudentSidebar.vue'

const items = ref<any[]>([])

onMounted(async () => {
  try {
    const res = await wrongbookApi.list()
    items.value = res.data || []
  } catch (e) {
    console.error('Failed to load wrong book:', e)
  }
})

function statusText(status: string): string {
  const map: Record<string, string> = {
    not_reviewed: '未复盘', reviewing: '复习中', consolidating: '巩固中', mastered: '已掌握',
  }
  return map[status] || status
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
  margin-left: 240px;
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
  justify-content: space-between;
  margin-bottom: 12rpx;
}
.q-no {
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
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
</style>
