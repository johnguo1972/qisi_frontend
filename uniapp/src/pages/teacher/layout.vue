<template>
  <view class="layout">
    <TeacherSidebar :activeItem="currentPage" @navigate="switchPage" />
    <view class="content-area">
      <!-- MP-WEIXIN 不支持动态组件，使用条件渲染保持相同的页面切换行为。 -->
      <WorkbenchPage v-if="currentPage === 'workbench'" />
      <QuestionBankPage v-else-if="currentPage === 'question-bank'" />
      <FavoritesPage v-else-if="currentPage === 'favorites'" />
      <MyClassesPage v-else-if="currentPage === 'student-management'" />
      <MissionListPage v-else-if="currentPage === 'assignment-list'" />
      <CourseListPage v-else-if="currentPage === 'course-list'" />
      <LearningStatsPage v-else-if="currentPage === 'learning-stats'" />
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TeacherSidebar from '@/components/TeacherSidebar.vue'
import WorkbenchPage from './workbench.vue'
import QuestionBankPage from './question-bank.vue'
import FavoritesPage from './favorites.vue'
import MyClassesPage from './my-classes.vue'
import MissionListPage from './mission-list.vue'
import CourseListPage from './course-list.vue'
import LearningStatsPage from './learning-stats.vue'

const currentPage = ref('workbench')

const components: Record<string, any> = {
  workbench: WorkbenchPage,
  'question-bank': QuestionBankPage,
  favorites: FavoritesPage,
  'course-list': CourseListPage,
  'student-management': MyClassesPage,
  'assignment-list': MissionListPage,
  'learning-stats': LearningStatsPage,
}

function switchPage(page: string) {
  if (components[page]) currentPage.value = page
}
</script>

<style>
.layout {
  display: flex;
  width: 100%;
  min-width: 0;
  height: 100vh;
  min-height: 0;
  box-sizing: border-box;
  background: #f0f2f5;
  overflow: hidden;
}
.content-area {
  margin-left: 240px;
  flex: 1;
  width: calc(100% - 240px);
  min-width: 0;
  height: 100vh;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
  overflow: hidden;
  padding: 30rpx 40rpx;
}

@media (max-width: 768px) {
  .content-area { padding: 16rpx 20rpx; }
}
</style>
