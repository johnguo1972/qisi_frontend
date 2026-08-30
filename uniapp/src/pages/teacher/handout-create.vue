<template>
  <view class="page">
    <view class="card">
      <text class="title">创建讲义</text>
      <text class="hint">题库中选中的题目会按当前顺序写入快照。</text>
      <input v-model="name" class="input" placeholder="讲义名称" />
      <input v-model="courseId" class="input" placeholder="课程 ID（可选，发布前必须填写）" />
      <input v-model="classIdsText" class="input" placeholder="班级 ID（多个用逗号分隔，可选）" />
      <input v-model="grade" class="input" placeholder="年级（可选，例如：9）" />
      <view class="summary">已选择 {{ questionIds.length }} 道题</view>
      <button class="primary" :loading="saving" @click="save">保存讲义</button>
      <button v-if="handoutId" class="secondary" @click="preview">预览讲义</button>
      <button v-if="handoutId" class="secondary" @click="publish">发布讲义</button>
      <button v-if="handoutId" class="secondary" @click="exportPdf">导出 PDF</button>
      <button v-if="handoutId && courseId" class="secondary" @click="attachToCourse">关联课程和班级</button>
      <button class="secondary" @click="goHandoutList">查看讲义列表</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app'
import { ref } from 'vue'
import { handoutApi } from '@/api/handouts'

const name = ref('')
const subject = ref('math')
const grade = ref('')
const courseId = ref('')
const classIdsText = ref('')
const questionIds = ref<string[]>([])
const handoutId = ref('')
const saving = ref(false)

onLoad(async (query: any) => {
  subject.value = query?.subject || 'math'
  questionIds.value = String(query?.questionIds || '').split(',').filter(Boolean)
  name.value = `讲义-${new Date().toISOString().slice(0, 10)}`
  if (query?.handoutId) {
    try {
      const detail: any = await handoutApi.detail(query.handoutId)
      const preview: any = await handoutApi.preview(query.handoutId)
      const item = detail.data || detail
      handoutId.value = query.handoutId
      name.value = item.name || name.value
      subject.value = item.subject || subject.value
      grade.value = item.grade || ''
      courseId.value = item.course || ''
      questionIds.value = (preview.data?.questions || []).map((row: any) => row.question_id).filter(Boolean)
    } catch (error: any) { uni.showToast({ title: error?.message || '讲义加载失败', icon: 'none' }) }
  }
})

async function save() {
  if (!name.value.trim() || !questionIds.value.length) {
    uni.showToast({ title: '请输入名称并至少选择一道题', icon: 'none' }); return
  }
  saving.value = true
  try {
    if (!handoutId.value) {
      const created: any = await handoutApi.create({ name: name.value.trim(), subject: subject.value, grade: grade.value, course: courseId.value || undefined })
      handoutId.value = created.data?.id || created.id
    }
    await handoutApi.replaceQuestions(handoutId.value, questionIds.value)
    uni.showToast({ title: '讲义已保存', icon: 'success' })
  } catch (error: any) { uni.showToast({ title: error?.message || '保存失败', icon: 'none' }) }
  finally { saving.value = false }
}

async function preview() {
  try { const result: any = await handoutApi.preview(handoutId.value); uni.showModal({ title: '讲义预览', content: `共 ${result.data?.questions?.length || 0} 道题`, showCancel: false }) }
  catch (error: any) { uni.showToast({ title: error?.message || '预览失败', icon: 'none' }) }
}
async function publish() { try { await handoutApi.publish(handoutId.value); uni.showToast({ title: '已发布', icon: 'success' }) } catch (error: any) { uni.showToast({ title: error?.message || '发布失败', icon: 'none' }) } }
async function exportPdf() { try { const result: any = await handoutApi.exportPdf(handoutId.value); uni.setClipboardData({ data: result.data?.download_url || '' }); uni.showToast({ title: 'PDF 链接已复制', icon: 'success' }) } catch (error: any) { uni.showToast({ title: error?.message || '导出失败', icon: 'none' }) } }
async function attachToCourse() {
  try {
    await handoutApi.attachHandout(courseId.value, handoutId.value)
    for (const classId of classIdsText.value.split(',').map(item => item.trim()).filter(Boolean)) await handoutApi.attachClass(courseId.value, classId)
    uni.showToast({ title: '课程和班级关联成功', icon: 'success' })
  } catch (error: any) { uni.showToast({ title: error?.message || '关联失败', icon: 'none' }) }
}
function goHandoutList() { uni.navigateTo({ url: '/pages/teacher/handout-list' }) }
</script>

<style scoped>
.page { min-height: 100vh; padding: 32rpx; background: #f6f8fb; }
.card { max-width: 900rpx; margin: 0 auto; padding: 36rpx; background: #fff; border-radius: 18rpx; }
.title { display: block; margin-bottom: 18rpx; font-size: 40rpx; font-weight: 700; }
.hint, .summary { display: block; margin-bottom: 24rpx; color: #6b7280; }
.input { box-sizing: border-box; width: 100%; margin: 18rpx 0; padding: 20rpx; border: 1px solid #dce2ea; border-radius: 10rpx; }
button { margin-top: 18rpx; }
.primary { color: #fff; background: #2563eb; }
.secondary { color: #2563eb; background: #eef4ff; }
</style>
