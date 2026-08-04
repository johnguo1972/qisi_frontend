<template>
  <view class="layout">
    <TeacherSidebar :activeItem="currentPage" @navigate="switchPage" />
    <view class="content-area">
      <component :is="currentComponent" />
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
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

const currentComponent = computed(() => components[currentPage.value])

function switchPage(page: string) {
  if (components[page]) currentPage.value = page
}
</script>

<style>
.layout {
  display: flex;
  width: 100%;
  height: 100vh;
  min-height: 0;
  background: #f0f2f5;
  overflow: hidden;
}
.content-area {
  margin-left: 240px;
  flex: 1;
  width: calc(100% - 240px);
  height: 100vh;
  min-width: 0;
  min-height: 0;
  box-sizing: border-box;
  overflow: hidden;
  padding: 30rpx 40rpx;
}
</style>
