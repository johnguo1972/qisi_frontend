<template>
  <view class="layout">
    <StudentSidebar :activeItem="currentPage" @navigate="switchPage" />
    <view class="content-area">
      <!-- MP-WEIXIN 不支持动态组件，使用条件渲染保持相同的页面切换行为。 -->
      <HomePage v-if="currentPage === 'home'" />
      <WrongbookPage v-else-if="currentPage === 'wrongbook'" />
      <GrowthPage v-else-if="currentPage === 'growth'" />
      <JoinClassPage v-else-if="currentPage === 'join-class'" />
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import StudentSidebar from '@/components/StudentSidebar.vue'
import HomePage from './home.vue'
import WrongbookPage from './wrongbook.vue'
import GrowthPage from './growth.vue'
import JoinClassPage from './join-class.vue'

const currentPage = ref('home')

// layout 页面从答题/关卡页面返回时，通知首页重新拉取任务进度
onShow(() => {
  uni.$emit('student-layout-show')
})

function switchPage(page: string) {
  currentPage.value = page
}
</script>

<style>
.layout {
  display: flex;
  width: 100%;
  min-width: 0;
  min-height: 100vh;
  box-sizing: border-box;
  background: #f0f2f5;
}
.content-area {
  margin-left: 240px;
  flex: 1;
  min-width: 0;
  box-sizing: border-box;
  padding: 30rpx 40rpx;
}

@media (max-width: 768px) {
  .content-area { padding: 16rpx 20rpx; }
}
</style>
