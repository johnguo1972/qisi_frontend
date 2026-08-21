<template>
  <view class="page">
    <MpChildSwitcher v-if="isParent" :visible="true" @changed="load" />
    <view class="quick"><button @click="drawer = true"><text class="quick-label">☰ 菜单</text></button><button @click="inputCode"><text class="quick-label">📝 输入作业码</text></button><button @click="goScan"><text class="quick-label">⌕ 扫码进入</text></button></view>
    <MpClassSelector :classes="classes" :selected="classId" :scope="scope" @class="classId = $event; load()" @scope="scope = $event; load()" />
    <view class="content"><view v-if="loading" class="empty">加载中...</view><view v-else-if="!missions.length" class="empty">暂无作业，等待老师发布吧</view><MpMissionCard v-for="m in missions" :key="m.mission?.id" :mission-id="String(m.mission?.id)" :mission-name="m.mission?.mission_name || m.mission_name" :class-label="m.class_label" :status="m.progress_status || 'not_started'" :level-count="m.level_count || 0" :question-count="m.question_count || 0" :assignment-mode="m.assignment_mode" :end-at="m.mission?.deadline || m.end_at" :progress-percent="m.progress_percent || 0" :pdf-download-url="m.pdf_download_url" @click="goMission" /></view>
    <MpDrawer :visible="drawer" :user-name="userName" @close="drawer = false" @navigate="navigate" @logout="logout" />
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import MpDrawer from '@/components/MpDrawer.vue'
import MpMissionCard from '@/components/MpMissionCard.vue'
import MpClassSelector from '@/components/MpClassSelector.vue'
import MpChildSwitcher from '@/components/MpChildSwitcher.vue'
import { studentApi } from '@/api/student'
import { scanCode, parseShortCode } from '@/utils/scan'

const drawer = ref(false); const loading = ref(false); const missions = ref<any[]>([]); const classes = ref<any[]>([]); const classId = ref(''); const scope = ref('all')
const userName = ref(uni.getStorageSync('userInfo')?.display_name || '同学')
const isParent = ref(uni.getStorageSync('userInfo')?.active_role === 'parent')
async function load() { loading.value = true; try { const r: any = await studentApi.home({ ...(classId.value ? { class_id: classId.value } : {}), scope: scope.value }, Date.now()); missions.value = r.data?.missions || []; classes.value = (r.data?.classes || []).map((c: any) => ({ id: c.id, label: c.name || c.class_name || c.label })) } finally { loading.value = false } }
function inputCode() { uni.showModal({ title: '输入作业码', editable: true, placeholderText: '请输入6位作业码', success: r => { if (r.confirm && r.content) uni.navigateTo({ url: `/pages/student/scan-entry?code=${r.content}` }) } }) }
async function goScan() { try { const r = await scanCode(); const code = parseShortCode(r.result); if (code) uni.navigateTo({ url: `/pages/student/scan-entry?code=${code}` }); else uni.showToast({ title: '无法识别作业二维码', icon: 'none' }) } catch (e: any) { uni.showToast({ title: e.message || '扫码已取消', icon: 'none' }) } }
function goMission(id: string) { uni.navigateTo({ url: `/pages/student/mission?id=${id}` }) }
function navigate(key: string) {
  drawer.value = false
  if (key === 'home') return
  if (key === 'wrongbook' || key === 'growth') {
    uni.switchTab({ url: `/pages/student/${key}` })
    return
  }
  if (key === 'practice') {
    uni.navigateTo({ url: '/pages/student/practice' })
    return
  }
  const routes: Record<string, string> = {
    knowledge: '/pages/student/knowledge-graph',
    'join-class': '/pages/student/join-class',
    'parent-bind': '/pages/student/parent-bind-requests',
    export: '/pages/student/export',
  }
  if (routes[key]) uni.navigateTo({ url: routes[key] })
}
function logout() { uni.clearStorageSync(); uni.reLaunch({ url: '/pages/login/index' }) }
onMounted(load); onShow(load)
</script>

<style scoped>.page{min-height:100vh;background:#f0f2f5;padding-bottom:30rpx;box-sizing:border-box}.quick{display:flex;gap:12rpx;padding:20rpx;box-sizing:border-box}.quick button{display:flex;align-items:center;justify-content:center;flex:1;min-width:0;height:72rpx;line-height:1;margin:0;padding:0 6rpx;background:#fff;color:#409eff;border-radius:14rpx;font-size:23rpx;white-space:nowrap;box-sizing:border-box}.quick-label{display:flex;align-items:center;justify-content:center;width:100%;height:100%;line-height:1;text-align:center}.content{padding:0 20rpx;box-sizing:border-box}.empty{text-align:center;color:#999;padding:100rpx 0;font-size:26rpx}</style>
