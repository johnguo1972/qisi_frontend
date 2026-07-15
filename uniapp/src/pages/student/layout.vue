<template>
  <view class="layout">
    <StudentSidebar :activeItem="currentPage" @navigate="switchPage" />
    <view class="content-area">
      <component :is="currentComponent" />
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import StudentSidebar from '@/components/StudentSidebar.vue'
import HomePage from './home.vue'
import WrongbookPage from './wrongbook.vue'
import GrowthPage from './growth.vue'
import JoinClassPage from './join-class.vue'

const currentPage = ref('home')

const components: Record<string, any> = {
  home: HomePage,
  wrongbook: WrongbookPage,
  growth: GrowthPage,
  'join-class': JoinClassPage,
}

const currentComponent = computed(() => components[currentPage.value])

function switchPage(page: string) {
  currentPage.value = page
}
</script>

<style>
.layout {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.content-area {
  margin-left: 240px;
  flex: 1;
  padding: 30rpx 40rpx;
}
</style>