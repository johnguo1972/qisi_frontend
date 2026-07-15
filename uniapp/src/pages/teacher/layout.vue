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
import ImportPage from './import.vue'
import NewQuestionPage from './new-question.vue'
import BankPage from './bank.vue'
import FavoritesPage from './favorites.vue'
import MyClassesPage from './my-classes.vue'
import MissionListPage from './mission-list.vue'

const currentPage = ref('workbench')

const components: Record<string, any> = {
  workbench: WorkbenchPage,
  import: ImportPage,
  'new-question': NewQuestionPage,
  bank: BankPage,
  favorites: FavoritesPage,
  classes: MyClassesPage,
  missions: MissionListPage,
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