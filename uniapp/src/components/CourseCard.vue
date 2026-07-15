<template>
  <view class="course-card" @click="$emit('click', course)">
    <!-- Cover with subject-based gradient -->
    <view class="card-cover" :style="{ background: subjectGradient }">
      <text class="subject-icon">{{ subjectIcon }}</text>
      <text class="grade-badge">{{ course.grade_level }}</text>
    </view>

    <!-- Course info -->
    <view class="card-body">
      <text class="course-name">{{ course.name }}</text>
      <text class="course-desc">{{ course.description || '暂无简介' }}</text>

      <!-- Stats -->
      <view class="card-stats">
        <view class="stat-item">
          <text class="stat-num">{{ course.material_count ?? 0 }}</text>
          <text class="stat-label">资料</text>
        </view>
        <view class="stat-item">
          <text class="stat-num">{{ course.question_count ?? 0 }}</text>
          <text class="stat-label">习题</text>
        </view>
      </view>
    </view>

    <!-- Action buttons -->
    <view class="card-actions">
      <button class="action-btn" size="mini" @click.stop="$emit('materials', course)">课程资料</button>
      <button class="action-btn primary" size="mini" @click.stop="$emit('practice', course)">课程练习</button>
      <view class="delete-btn" @click.stop="$emit('delete', course)">
        <text class="delete-icon">&times;</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Course {
  id: number
  name: string
  description?: string
  subject: string
  grade_level: string
  material_count?: number
  question_count?: number
}

const props = defineProps<{
  course: Course
}>()

defineEmits<{
  click: [course: Course]
  materials: [course: Course]
  practice: [course: Course]
  delete: [course: Course]
}>()

// Subject-to-color mapping for gradient covers
const subjectColors: Record<string, [string, string]> = {
  '数学': ['#667eea', '#764ba2'],
  '语文': ['#f093fb', '#f5576c'],
  '英语': ['#4facfe', '#00f2fe'],
  '物理': ['#43e97b', '#38f9d7'],
  '化学': ['#fa709a', '#fee140'],
  '生物': ['#a8edea', '#fed6e3'],
  '历史': ['#d299c2', '#fef9d7'],
  '地理': ['#89f7fe', '#66a6ff'],
  '政治': ['#ffecd2', '#fcb69f'],
}

const subjectGradient = computed(() => {
  const colors = subjectColors[props.course.subject] || ['#667eea', '#764ba2']
  return `linear-gradient(135deg, ${colors[0]}, ${colors[1]})`
})

const subjectIcon = computed(() => {
  const icons: Record<string, string> = {
    '数学': '📐',
    '语文': '📖',
    '英语': '🔤',
    '物理': '⚡',
    '化学': '🧪',
    '生物': '🧬',
    '历史': '📜',
    '地理': '🌍',
    '政治': '⚖️',
  }
  return icons[props.course.subject] || '📚'
})
</script>

<style scoped>
.course-card {
  background: #fff;
  border-radius: 12rpx;
  overflow: hidden;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.08);
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: pointer;
}

.course-card:hover {
  transform: translateY(-4rpx);
  box-shadow: 0 6rpx 20rpx rgba(0, 0, 0, 0.12);
}

/* Cover */
.card-cover {
  height: 180rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
}

.subject-icon {
  font-size: 56rpx;
  filter: drop-shadow(0 2rpx 4rpx rgba(0, 0, 0, 0.2));
}

.grade-badge {
  position: absolute;
  top: 12rpx;
  right: 12rpx;
  background: rgba(255, 255, 255, 0.9);
  color: #303133;
  font-size: 20rpx;
  padding: 4rpx 12rpx;
  border-radius: 20rpx;
  font-weight: 500;
}

/* Body */
.card-body {
  padding: 20rpx;
}

.course-name {
  font-size: 28rpx;
  font-weight: 600;
  color: #303133;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 8rpx;
}

.course-desc {
  font-size: 22rpx;
  color: #909399;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 12rpx;
}

/* Stats */
.card-stats {
  display: flex;
  gap: 24rpx;
  padding-top: 8rpx;
  border-top: 1rpx solid #f0f0f0;
}

.stat-item {
  display: flex;
  align-items: baseline;
  gap: 4rpx;
}

.stat-num {
  font-size: 26rpx;
  font-weight: 600;
  color: #409eff;
}

.stat-label {
  font-size: 20rpx;
  color: #909399;
}

/* Actions */
.card-actions {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 20rpx;
  border-top: 1rpx solid #f0f0f0;
}

.action-btn {
  margin: 0;
  font-size: 22rpx;
  padding: 4rpx 16rpx;
  height: auto;
  line-height: 1.4;
  background: #f5f7fa;
  color: #606266;
  border: none;
  border-radius: 6rpx;
}

.action-btn::after {
  border: none;
}

.action-btn.primary {
  background: #ecf5ff;
  color: #409eff;
}

.delete-btn {
  margin-left: auto;
  width: 44rpx;
  height: 44rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #f5f7fa;
  transition: background 0.2s;
}

.delete-btn:hover {
  background: #fef0f0;
}

.delete-icon {
  font-size: 32rpx;
  color: #f56c6c;
  font-weight: 300;
  line-height: 1;
}
</style>
