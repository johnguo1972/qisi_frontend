<template>
  <view class="page">
    <view class="card">
      <text class="title">纸质作业扫描</text>
      <input v-model="missionId" placeholder="输入作业ID" class="input" />
      <input v-model="studentCode" maxlength="8" placeholder="学生码" class="input" />
      <input v-model="missionCode" maxlength="6" placeholder="作业码" class="input" />
      <input v-model.number="pageNo" type="number" placeholder="页码" class="input" />
      <button type="primary" @click="createBatch">创建扫描批次</button>
      <button v-if="batchId" class="upload" @click="chooseImage">选择并上传页面</button>
      <text v-if="batchId" class="hint">批次：{{ batchId }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { qrcodeApi } from '@/api/index'
import { post } from '@/utils/request'

const missionId = ref('')
const studentCode = ref('')
const missionCode = ref('')
const pageNo = ref(1)
const batchId = ref('')

onLoad((options: any) => {
  if (options?.studentCode) studentCode.value = String(options.studentCode).toUpperCase()
  if (options?.missionCode) missionCode.value = String(options.missionCode).toUpperCase()
  if (options?.pageNo) pageNo.value = Number(options.pageNo) || 1
})

async function createBatch() {
  try { const res: any = await post('/paper-scan/batches', { mission_id: missionId.value }); batchId.value = res.data.batch_id; uni.showToast({ title: '批次已创建', icon: 'success' }) }
  catch { uni.showToast({ title: '创建批次失败', icon: 'none' }) }
}
function chooseImage() {
  uni.chooseImage({ count: 1, success: (result: any) => upload(result.tempFilePaths[0]) })
}
function upload(path: string) {
  const token = uni.getStorageSync('accessToken')
  uni.uploadFile({ url: '/api/v1/paper-scan/batches/' + batchId.value + '/pages', filePath: path, name: 'image', formData: { student_code: studentCode.value, mission_code: missionCode.value, page_no: String(pageNo.value) }, header: token ? { Authorization: `Bearer ${token}` } : {}, success: () => uni.showToast({ title: '页面已上传', icon: 'success' }), fail: () => uni.showToast({ title: '上传失败', icon: 'none' }) })
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 32rpx; background: #f5f7fa; box-sizing: border-box; }
.card { padding: 32rpx; background: #fff; border-radius: 16rpx; }
.title { display: block; margin-bottom: 28rpx; font-size: 36rpx; font-weight: 700; }
.input { width: 100%; height: 84rpx; box-sizing: border-box; margin-bottom: 20rpx; padding: 20rpx; border: 1px solid #dcdfe6; border-radius: 8rpx; }
.upload { margin-top: 20rpx; }
.hint { display: block; margin-top: 24rpx; color: #606266; word-break: break-all; }
</style>
