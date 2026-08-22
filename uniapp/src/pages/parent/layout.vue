<template>
  <ParentShell :active-item="currentPage" :inline="true" @section-change="switchPage">
    <!-- 统一家长端容器：菜单只切换右侧内容，不重新打开菜单页面。 -->
    <HomePage v-if="currentPage === 'home'" />
    <BindPage v-else-if="currentPage === 'children'" />
    <WrongbookPage v-else-if="currentPage === 'wrongbook'" />
    <PracticePage v-else-if="currentPage === 'practice'" />
    <GrowthPage v-else-if="currentPage === 'growth'" />
    <KnowledgePage v-else-if="currentPage === 'knowledge'" />
  </ParentShell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { ensurePageRole } from '@/utils/roles'
import ParentShell from '@/components/ParentShell.vue'
import HomePage from './home.vue'
import BindPage from './bind.vue'
import WrongbookPage from './wrongbook.vue'
import GrowthPage from './growth.vue'
import KnowledgePage from './knowledge.vue'
import PracticePage from '@/components/ParentPracticeContent.vue'

const currentPage = ref('home')

onShow(() => {
  ensurePageRole('parent')
})

function switchPage(page: string) {
  if (['home', 'children', 'wrongbook', 'practice', 'growth', 'knowledge'].includes(page)) {
    currentPage.value = page
  }
}
</script>
