<template>
  <view class="class-selector">
    <view class="selector-header" @click="toggleDropdown">
      <text class="selector-title">{{ currentClassName }}</text>
      <text class="selector-arrow">{{ expanded ? '&#9650;' : '&#9660;' }}</text>
    </view>

    <view v-if="expanded" class="selector-dropdown">
      <view
        v-for="cls in classes"
        :key="cls.id"
        class="class-item"
        :class="{ active: selectedClassId === cls.id }"
        @click="handleSelect(cls.id)"
      >
        <text class="class-name">{{ cls.class_name }}</text>
        <text v-if="cls.id === selectedClassId" class="check-mark">&#10003;</text>
      </view>

      <view class="class-item class-all" @click="handleSelect(0)">
        <text class="class-name">全部班级</text>
        <text v-if="selectedClassId === 0" class="check-mark">&#10003;</text>
      </view>

      <view class="join-btn" @click="handleJoin">
        <text class="join-text">+ 加入新班级</text>
      </view>

      <view v-if="classes.length === 0" class="empty-state">
        <text class="empty-text">还没有班级</text>
        <view class="empty-btn" @click.stop="handleJoin">
          <text class="empty-btn-text">去加入</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { studentClassApi } from '@/api/index.ts'

const emit = defineEmits<{
  select: [classId: number]
  join: []
}>()

interface ClassItem {
  id: number
  class_name: string
}

const classes = ref<ClassItem[]>([])
const selectedClassId = ref<number>(0)
const expanded = ref(false)
const loading = ref(false)

const currentClassName = computed(() => {
  if (selectedClassId.value === 0) return '全部班级'
  const cls = classes.value.find(c => c.id === selectedClassId.value)
  return cls ? cls.class_name : '选择班级'
})

async function loadClasses() {
  loading.value = true
  try {
    const res = await studentClassApi.myClasses()
    classes.value = res.data?.items || res.data || []
  } catch (e) {
    classes.value = []
  } finally {
    loading.value = false
  }
}

function toggleDropdown() {
  expanded.value = !expanded.value
}

function handleSelect(classId: number) {
  selectedClassId.value = classId
  expanded.value = false
  emit('select', classId)
}

function handleJoin() {
  expanded.value = false
  emit('join')
}

onMounted(() => {
  loadClasses()
})

defineExpose({ refresh: loadClasses })
</script>

<style scoped>
.class-selector {
  position: relative;
  width: 100%;
  min-width: 200px;
}

.selector-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12rpx 24rpx;
  background: #fff;
  border: 1rpx solid #d9ecff;
  border-radius: 12rpx;
  cursor: pointer;
  transition: all 0.2s;
}

.selector-header:hover {
  border-color: #409eff;
  background: #ecf5ff;
}

.selector-title {
  font-size: 28rpx;
  color: #333;
  font-weight: 500;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.selector-arrow {
  font-size: 24rpx;
  color: #999;
  margin-left: 12rpx;
}

.selector-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 8rpx;
  background: #fff;
  border: 1rpx solid #ebeef5;
  border-radius: 12rpx;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);
  z-index: 100;
  max-height: 500rpx;
  overflow-y: auto;
}

.class-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 24rpx;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1rpx solid #f0f0f0;
}

.class-item:last-of-type {
  border-bottom: none;
}

.class-item:hover {
  background: #f5f7fa;
}

.class-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.class-name {
  font-size: 28rpx;
  color: #333;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.class-item.active .class-name {
  color: #409eff;
  font-weight: 500;
}

.check-mark {
  font-size: 28rpx;
  color: #409eff;
  margin-left: 12rpx;
}

.join-btn {
  padding: 20rpx 24rpx;
  text-align: center;
  cursor: pointer;
  background: #fafcff;
  border-top: 1rpx dashed #d9ecff;
  transition: background 0.15s;
}

.join-btn:hover {
  background: #ecf5ff;
}

.join-text {
  font-size: 26rpx;
  color: #409eff;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40rpx 24rpx;
}

.empty-text {
  font-size: 26rpx;
  color: #999;
  margin-bottom: 20rpx;
}

.empty-btn {
  padding: 12rpx 32rpx;
  background: #409eff;
  border-radius: 8rpx;
  cursor: pointer;
  transition: background 0.2s;
}

.empty-btn:hover {
  background: #3a8ee6;
}

.empty-btn-text {
  font-size: 24rpx;
  color: #fff;
}
</style>
