<template>
  <view class="page">
    <MpChildSwitcher :visible="true" @changed="onChildChanged" />
    <view v-if="!selectedChild" class="state-card">请先绑定并选择孩子</view>
    <PracticeContent v-else :key="String(selectedChild.id)" :readonly="false" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import MpChildSwitcher from '@/components/MpChildSwitcher.vue'
import PracticeContent from '@/components/PracticeContent.vue'

const selectedChild = ref<any>(null)

function onChildChanged(child: any) {
  selectedChild.value = child
}
</script>

<style scoped>
.page { width: 100%; }
.state-card { margin: 24rpx; padding: 70rpx 30rpx; border-radius: 18rpx; background: #fff; color: #909399; text-align: center; font-size: 25rpx; }
</style>
