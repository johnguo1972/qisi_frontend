<template>
  <view class="page">
    <view class="header">
      <view><text class="title">错题统计</text><text class="subtitle">{{ matrix?.mission_name || '' }}</text></view>
      <view class="actions">
        <view class="manual-help">ⓘ 点击“手动统计错题”可以直接在表格中对学生的错题进行操作</view>
        <picker class="class-picker" :range="classLabels" :value="classIndex" @change="changeClass">
          <button size="mini">{{ classLabels[classIndex] || '选择班级' }}</button>
        </picker>
        <button size="mini" @click="load">刷新</button>
        <button size="mini" @click="chooseImportFile">导入错题统计</button>
        <button size="mini" :type="manualEditing ? 'primary' : 'default'" @click="toggleManual">{{ manualEditing ? '保存统计' : '手动统计错题' }}</button>
        <button v-if="manualEditing" size="mini" @click="cancelManual">取消</button>
        <button size="mini" type="primary" @click="generateDrill">生成精练题</button>
      </view>
    </view>

    <view v-if="loading" class="empty">正在加载...</view>
    <view v-else-if="errorMessage" class="error">{{ errorMessage }}</view>
    <template v-else-if="matrix">
      <view class="summary">
        <view class="stat"><text>总练习题数</text><strong>{{ matrix.summary.total_practice_count }}</strong></view>
        <view class="stat"><text>学生人数</text><strong>{{ matrix.summary.student_count }}</strong></view>
        <view class="stat"><text>累计错题</text><strong>{{ liveSummary.accumulated_wrong_count }}</strong></view>
        <view class="stat"><text>人均错题</text><strong>{{ liveSummary.average_wrong_count }}</strong></view>
      </view>
      <view class="workspace">
        <view class="nodes">
          <text class="section-title">讲义节点</text>
          <view v-for="node in matrix.nodes" :key="node.node_id" :class="['node', { active: node.node_id === selectedNodeId }]" @click="selectedNodeId = node.node_id">
            {{ node.node_name }}（{{ node.question_count }}题）
          </view>
        </view>
        <view class="matrix-wrap">
          <scroll-view scroll-x class="matrix-scroll">
            <view class="matrix-table" :style="{ minWidth: `${430 + visibleQuestions.length * 76}px` }">
              <view class="matrix-row matrix-header"><text class="serial-col">序号</text><text class="student-col">学生</text><text v-for="question in visibleQuestions" :key="question.question_id" class="question-col">{{ question.question_no }}</text><text class="rate-col">错题率</text></view>
              <view v-for="(student, index) in matrix.students" :key="student.student_id" class="matrix-row">
                <text class="serial-col">{{ index + 1 }}</text><text class="student-col"><text>{{ student.student_name }}</text><text v-if="student.data_source === 'online'" class="lock-hint">线上已答，人工统计已锁定</text></text>
                <text v-for="question in visibleQuestions" :key="question.question_id" class="question-col cell" :class="{ editable: manualEditing && !isOnline(student.student_id) }" @click="toggleCell(student.student_id, question.question_id)">{{ displayWrong(student.student_id, question.question_id) ? '❌' : '' }}</text>
                <text class="rate-col">{{ studentWrongRate(student.student_id) }}%</text>
              </view>
            </view>
          </scroll-view>
          <view v-if="!visibleQuestions.length" class="empty">当前节点暂无练习题</view>
        </view>
      </view>
      <view class="legend">线上答题错题自动生成；线上学生单元格只读。线下学生可手动统计或导入。</view>
      <view v-if="matrix.latest_import" class="import-result">最近导入：{{ matrix.latest_import.file_name }}，成功 {{ matrix.latest_import.imported_count }}，取消 {{ matrix.latest_import.cancelled_count }}，跳过 {{ matrix.latest_import.skipped_count }}</view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classroomWrongbookApi } from '@/api/classroom-wrongbook'

const matrix = ref<any | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const selectedNodeId = ref('')
const classId = ref('')
const manualEditing = ref(false)
const editedMarks = ref<Record<string, boolean>>({})
const missionId = ref('')
const classOptions = ref<Array<{ class_id: string; class_name: string }>>([])
const classLabels = computed(() => classOptions.value.map(item => item.class_name))
const classIndex = computed(() => {
  const index = classOptions.value.findIndex(item => item.class_id === classId.value)
  return index >= 0 ? index : 0
})

const visibleQuestions = computed(() => (matrix.value?.questions || []).filter((item: any) => !selectedNodeId.value || item.node_id === selectedNodeId.value))
const liveSummary = computed(() => {
  const students = matrix.value?.students || []
  const accumulatedWrongCount = students.reduce((sum: number, student: any) => sum + studentWrongCount(student.student_id), 0)
  return {
    accumulated_wrong_count: accumulatedWrongCount,
    average_wrong_count: students.length ? Number((accumulatedWrongCount / students.length).toFixed(2)) : 0,
  }
})

onLoad((options: any) => {
  missionId.value = String(options?.mission_id || '')
  classId.value = String(options?.class_id || '')
  load()
})

async function load() {
  if (!missionId.value) { errorMessage.value = '缺少课堂练习参数'; return }
  loading.value = true
  errorMessage.value = ''
  try {
    const response: any = await classroomWrongbookApi.statistics(missionId.value, classId.value ? { class_id: classId.value } : undefined)
    if (response?.code !== 0) throw new Error(response?.message || '加载失败')
    matrix.value = response.data
    classOptions.value = Array.isArray(matrix.value.class_options)
      ? matrix.value.class_options.map((item: any) => ({
        class_id: String(item.class_id),
        class_name: item.class_name || String(item.class_id),
      }))
      : []
    if (classOptions.value.length) {
      const selected = classOptions.value.find(item => item.class_id === classId.value)
        || classOptions.value.find(item => item.class_id === String(matrix.value.class_id))
        || classOptions.value[0]
      classId.value = selected.class_id
    }
    if (!selectedNodeId.value) selectedNodeId.value = matrix.value.nodes?.[0]?.node_id || ''
  } catch (error: any) {
    errorMessage.value = error?.message || '错题统计加载失败'
  } finally { loading.value = false }
}

function changeClass(event: any) {
  const option = classOptions.value[Number(event?.detail?.value)]
  if (!option || option.class_id === classId.value) return
  classId.value = option.class_id
  selectedNodeId.value = ''
  editedMarks.value = {}
  manualEditing.value = false
  load()
}

function key(studentId: string, questionId: string) { return `${studentId}:${questionId}` }
function baseWrong(studentId: string, questionId: string) {
  const student = matrix.value?.students?.find((item: any) => item.student_id === studentId)
  return !!student?.cells?.find((cell: any) => cell.source_question_id === questionId)?.wrong
}
function displayWrong(studentId: string, questionId: string) {
  const value = editedMarks.value[key(studentId, questionId)]
  return value === undefined ? baseWrong(studentId, questionId) : value
}
function studentWrongCount(studentId: string) {
  return (matrix.value?.questions || []).reduce(
    (count: number, question: any) => count + Number(displayWrong(studentId, question.question_id)),
    0,
  )
}
function studentWrongRate(studentId: string) {
  const questions = visibleQuestions.value
  const wrongCount = questions.reduce(
    (count: number, question: any) => count + Number(displayWrong(studentId, question.question_id)),
    0,
  )
  return questions.length ? Number((wrongCount / questions.length * 100).toFixed(2)) : 0
}
function isOnline(studentId: string) {
  return matrix.value?.students?.find((item: any) => item.student_id === studentId)?.data_source === 'online'
}
function toggleCell(studentId: string, questionId: string) {
  if (!manualEditing.value || isOnline(studentId)) return
  const current = displayWrong(studentId, questionId)
  editedMarks.value[key(studentId, questionId)] = !current
}
function toggleManual() {
  if (manualEditing.value) saveManual()
  else { editedMarks.value = {}; manualEditing.value = true }
}
function cancelManual() { editedMarks.value = {}; manualEditing.value = false }

async function saveManual() {
  const cells = Object.entries(editedMarks.value).map(([cellKey, wrong]) => {
    const [student_id, source_question_id] = cellKey.split(':')
    return { student_id, source_question_id, wrong }
  })
  if (!cells.length) { manualEditing.value = false; return }
  try {
    const response: any = await classroomWrongbookApi.save(missionId.value, { class_id: classId.value, version: matrix.value.version, cells })
    if (response?.code !== 0) {
      if (response?.code === 409) { editedMarks.value = {}; manualEditing.value = false; await load() }
      throw new Error(response?.message || '保存失败')
    }
    matrix.value = response.data
    editedMarks.value = {}
    manualEditing.value = false
    uni.showToast({ title: '错题统计已保存', icon: 'success' })
  } catch (error: any) { uni.showToast({ title: error?.message || '保存失败', icon: 'none' }) }
}

function chooseImportFile() {
  if (manualEditing.value) { uni.showToast({ title: '请先保存或取消手动统计', icon: 'none' }); return }
  // #ifdef MP-WEIXIN
  uni.chooseMessageFile({ count: 1, type: 'file', success: (result: any) => uploadFile(result.tempFiles?.[0]?.path) })
  // #endif
  // #ifndef MP-WEIXIN
  ;(uni as any).chooseFile({ count: 1, extension: ['xlsx'], success: (result: any) => uploadFile(result.tempFiles?.[0]?.path) })
  // #endif
}
function uploadFile(filePath?: string) {
  if (!filePath) { uni.showToast({ title: '未选择文件', icon: 'none' }); return }
  classroomWrongbookApi.upload(missionId.value, filePath, { class_id: classId.value, version: matrix.value.version })
    .then((response: any) => { matrix.value = response.data.matrix; editedMarks.value = {}; manualEditing.value = false; uni.showToast({ title: '导入成功', icon: 'success' }) })
    .catch((error: any) => {
      if (error?.data?.code === 409) { editedMarks.value = {}; manualEditing.value = false; load() }
      const detail = error?.data?.data?.errors?.[0]?.message
      uni.showToast({ title: detail || error?.message || '导入失败', icon: 'none' })
    })
}
function generateDrill() {
  const wrongCount = (matrix.value?.students || []).reduce((sum: number, student: any) => sum + Number(student.wrong_count || 0), 0)
  if (manualEditing.value) { uni.showToast({ title: '请先保存错题统计', icon: 'none' }); return }
  if (!wrongCount) { uni.showToast({ title: '当前没有错题可以生成精练题，请手动统计或者导入错题', icon: 'none' }); return }
  uni.showToast({ title: '生成精练题功能将在下次开发', icon: 'none' })
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 28rpx; background: #f5f7fa; box-sizing: border-box; overflow-x: hidden; }
.header { display: flex; justify-content: space-between; align-items: center; gap: 20rpx; margin-bottom: 24rpx; }
.title { display: block; font-size: 36rpx; font-weight: 600; color: #303133; }.subtitle { display: block; margin-top: 8rpx; color: #909399; font-size: 24rpx; }.actions { display: flex; flex-wrap: wrap; gap: 12rpx; }.actions button { margin: 0; }
.summary { display: flex; gap: 16rpx; margin-bottom: 20rpx; }.stat { flex: 1; min-width: 150rpx; padding: 20rpx; background: #fff; border-radius: 10rpx; }.stat text,.stat strong { display: block; }.stat text { color: #909399; font-size: 23rpx; }.stat strong { margin-top: 10rpx; color: #303133; font-size: 34rpx; }
.workspace { display: flex; min-height: 520rpx; background: #fff; border-radius: 10rpx; overflow: hidden; }.nodes { width: 240rpx; flex: 0 0 240rpx; padding: 20rpx 0; background: #fafafa; }.section-title { display: block; padding: 0 20rpx 16rpx; color: #606266; font-weight: 600; }.node { padding: 20rpx; color: #606266; font-size: 24rpx; }.node.active { color: #409eff; background: #ecf5ff; border-right: 4rpx solid #409eff; }.matrix-wrap { flex: 1; min-width: 0; padding: 20rpx; }.matrix-scroll { width: 100%; }.matrix-table { border: 1rpx solid #ebeef5; }.matrix-row { display: flex; min-height: 76rpx; border-bottom: 1rpx solid #ebeef5; }.matrix-row:last-child { border-bottom: 0; }.matrix-header { background: #f5f7fa; font-weight: 600; }.student-col { flex: 0 0 180rpx; width: 180rpx; padding: 20rpx 12rpx; box-sizing: border-box; }.question-col { flex: 0 0 76rpx; width: 76rpx; padding: 20rpx 4rpx; box-sizing: border-box; text-align: center; border-left: 1rpx solid #ebeef5; }.cell { color: #f56c6c; font-size: 30rpx; }.rate-col { flex: 0 0 100rpx; width: 100rpx; padding: 20rpx 4rpx; box-sizing: border-box; text-align: center; }.legend { margin-top: 16rpx; color: #909399; font-size: 22rpx; }.empty { padding: 80rpx 0; color: #909399; text-align: center; }.error { padding: 60rpx; color: #f56c6c; background: #fff; }
.lock-hint { display: block; margin-top: 4rpx; color: #e6a23c; font-size: 18rpx; }
.import-result { margin-top: 16rpx; padding: 16rpx; color: #606266; background: #fff; border-radius: 8rpx; font-size: 22rpx; }
.manual-help { display: flex; align-items: center; align-self: center; height: 64rpx; color: #909399; font-size: 21rpx; line-height: 1.4; white-space: nowrap; }
.nodes { width: 420rpx; flex: 0 0 420rpx; }
.node { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; }
.rate-col { flex-basis: 150rpx; width: 150rpx; padding-left: 8rpx; padding-right: 8rpx; white-space: nowrap; }
.matrix-wrap { overflow: hidden; }
.matrix-scroll { max-width: 100%; overflow-x: auto; }
.cell.editable { cursor: pointer; }
.serial-col { flex: 0 0 100rpx; width: 100rpx; padding: 20rpx 8rpx; box-sizing: border-box; text-align: center; border-left: 1rpx solid #ebeef5; border-right: 1rpx solid #ebeef5; }
.question-col { border-left: 1rpx solid #ebeef5; border-right: 1rpx solid #ebeef5; }
.rate-col { border-left: 1rpx solid #ebeef5; border-right: 1rpx solid #ebeef5; }
.actions { align-items: center; min-height: 64rpx; }
.actions button,
.class-picker button { height: 64rpx; line-height: 64rpx; padding-top: 0; padding-bottom: 0; box-sizing: border-box; }
.class-picker { display: flex; align-items: center; height: 64rpx; }
</style>
