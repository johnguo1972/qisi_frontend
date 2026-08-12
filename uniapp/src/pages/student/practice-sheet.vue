<template>
  <view class="page">
    <view class="card">
      <text class="title">错题练习单</text>
      <input v-model="sheetCode" maxlength="6" placeholder="输入练习单二维码中的6位编码" class="input" />
      <button type="primary" :loading="loading" @click="loadSheet">查询练习单</button>
      <view v-if="sheet" class="detail">
        <text>学生：{{ sheet.student_name }}</text>
        <text>原题：{{ sheet.original_question_id }}</text>
        <text>模式：{{ sheet.mode }}</text>
        <textarea v-model="answers" placeholder="填写答案或备注" class="textarea" />
        <button type="primary" @click="submit">提交练习</button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { qrcodeApi } from '@/api/index'

const sheetCode = ref('')
const sheet = ref<any>(null)
const answers = ref('')
const loading = ref(false)

onLoad((options: any) => { if (options?.code) { sheetCode.value = String(options.code).toUpperCase(); loadSheet() } })
async function loadSheet() {
  sheetCode.value = sheetCode.value.trim().toUpperCase()
  if (!/^[A-Z0-9]{6}$/.test(sheetCode.value)) return uni.showToast({ title: '请输入6位练习单编码', icon: 'none' })
  loading.value = true
  try { const res: any = await qrcodeApi.practiceSheetInfo(sheetCode.value); sheet.value = res.data }
  catch { uni.showToast({ title: '练习单不存在或未登录', icon: 'none' }) }
  finally { loading.value = false }
}
async function submit() {
  try { await qrcodeApi.submitPracticeSheet(sheetCode.value, { answers: { text: answers.value }, submit_source: 'online' }); uni.showToast({ title: '提交成功', icon: 'success' }) }
  catch { uni.showToast({ title: '提交失败', icon: 'none' }) }
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 32rpx; background: #f5f7fa; box-sizing: border-box; }
.card { padding: 32rpx; background: #fff; border-radius: 16rpx; }
.title { display: block; margin-bottom: 28rpx; font-size: 36rpx; font-weight: 700; }
.input, .textarea { width: 100%; box-sizing: border-box; margin-bottom: 24rpx; padding: 20rpx; border: 1px solid #dcdfe6; border-radius: 8rpx; }
.input { height: 84rpx; letter-spacing: 6rpx; }
.textarea { height: 220rpx; }
.detail { display: flex; flex-direction: column; gap: 20rpx; margin-top: 32rpx; }
</style>
