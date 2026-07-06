<template>
  <view class="time-filter-bar">
    <view
      v-for="item in options"
      :key="item.value"
      class="pill"
      :class="{ active: modelValue === item.value }"
      @click="handleClick(item.value)"
    >
      <text class="pill-text" :class="{ active: modelValue === item.value }">
        {{ item.label }}
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
const props = defineProps<{
  modelValue?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: 'all' | 'today' | 'week'): void
}>()

interface FilterOption {
  label: string
  value: 'all' | 'today' | 'week'
}

const options: FilterOption[] = [
  { label: '全部', value: 'all' },
  { label: '今日', value: 'today' },
  { label: '本周', value: 'week' },
]

const handleClick = (value: 'all' | 'today' | 'week') => {
  emit('update:modelValue', value)
  emit('change', value)
}
</script>

<style scoped>
.time-filter-bar {
  display: flex;
  flex-direction: row;
  gap: 8px;
  padding: 8px 0;
}

.pill {
  padding: 6px 16px;
  border-radius: 20px;
  background-color: #f0f0f0;
  transition: all 0.2s ease;
}

.pill:active {
  opacity: 0.8;
}

.pill.active {
  background-color: #3b82f6;
}

.pill-text {
  font-size: 14px;
  color: #666;
}

.pill-text.active {
  color: #fff;
  font-weight: 500;
}
</style>
