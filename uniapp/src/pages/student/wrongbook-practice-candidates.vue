<template>
  <view class="page"><view class="header"><text class="title">关联题推荐</text><text class="meta">最多选择 3 道加入精练列表</text></view><view v-if="!candidates.length" class="empty">暂无符合规则的关联题</view><view v-for="item in candidates" :key="item.id" class="card" @click="toggle(item.id)"><checkbox class="check-box" :checked="selected.includes(String(item.id))" /><view class="body"><text class="meta">{{ item.question_type_label || '题目' }} · 难度 {{ item.difficulty_label || item.difficulty || '-' }}</text><text class="stem">{{ plain(item.stem || item.stem_html) }}</text><text class="meta">知识点：{{ (item.knowledge_point_labels || []).join('、') || '未标注' }}</text></view></view><button v-if="candidates.length" type="primary" :disabled="!selected.length || saving" @click="add">{{ saving ? '加入中...' : `加入精练列表（${selected.length}）` }}</button></view>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { practiceApi, wrongbookApi } from '@/api/student'
const wrongItemId = ref(''); const candidates = ref<any[]>([]); const selected = ref<string[]>([]); const saving = ref(false)
onLoad((options: any) => { wrongItemId.value = String(options?.id || '') })
onMounted(async () => {
  if (!wrongItemId.value) return
  let response: any = await practiceApi.wrongbookCandidates(wrongItemId.value)
  // #ifdef MP-WEIXIN
  // 兼容旧页面曾把 question_id 写入路由参数的情况，重新从错题本定位真正的 item.id。
  if (response?.code === 404) {
    try {
      const list: any = await wrongbookApi.list()
      const matched = (Array.isArray(list?.data) ? list.data : []).find((item: any) =>
        String(item?.id) === wrongItemId.value || String(item?.question_id) === wrongItemId.value,
      )
      if (matched?.id && String(matched.id) !== wrongItemId.value) {
        wrongItemId.value = String(matched.id)
        response = await practiceApi.wrongbookCandidates(wrongItemId.value)
      }
    } catch (error) {
      console.warn('兼容旧错题参数失败', error)
    }
  }
  // #endif
  if (response?.code === 0) {
    candidates.value = Array.isArray(response.data) ? response.data : []
  } else if (response?.message) {
    uni.showToast({ title: response.message, icon: 'none' })
  }
})
function plain(value: any) { return String(value || '暂无题干').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim() || '暂无题干' }
function toggle(id: string) { const value = String(id); const index = selected.value.indexOf(value); if (index >= 0) selected.value.splice(index, 1); else if (selected.value.length < 3) selected.value.push(value); else uni.showToast({ title: '最多选择 3 道', icon: 'none' }) }
async function add() { saving.value = true; try { const response: any = await practiceApi.addPoolItems({ items: selected.value.map(question_id => ({ question_id, source_wrong_item_id: wrongItemId.value, source_type: 'recommended_variant' })) }); if (response.code === 0) { uni.showToast({ title: '已加入精练列表', icon: 'success' }); setTimeout(() => uni.navigateBack(), 500) } } finally { saving.value = false } }
</script>
<style scoped>.page{min-height:100vh;padding:24rpx;background:#f0f2f5;box-sizing:border-box}.header{margin-bottom:20rpx}.title{display:block;color:#303133;font-size:34rpx;font-weight:700}.meta{display:block;margin-top:8rpx;color:#909399;font-size:22rpx}.card{display:flex;gap:14rpx;align-items:center;margin-bottom:14rpx;padding:22rpx;background:#fff;border-radius:12rpx}.check-box{display:flex;align-items:center;justify-content:center;flex:0 0 52rpx;width:52rpx;height:52rpx;margin:0}.body{flex:1;min-width:0}.stem{display:block;margin-top:12rpx;color:#303133;font-size:26rpx;line-height:1.6}.empty{padding:100rpx 20rpx;color:#909399;text-align:center}button{margin-top:22rpx}</style>
