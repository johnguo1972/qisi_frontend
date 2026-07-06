<template>
  <view class="answer-page">
    <!-- 左侧题目区 -->
    <view class="question-panel">
      <view class="question-header">
        <text class="q-no">第 {{ currentIndex + 1 }}/{{ questions.length }} 题</text>
        <text class="q-type">{{ currentQuestion.question_type }}</text>
      </view>

      <!-- 客观题：选项 -->
      <view v-if="isObjective" class="options-grid">
        <view v-for="opt in currentQuestion.options" :key="opt.label"
              class="option-card" :class="{ selected: selectedOptions.includes(opt.label) }"
              @click="toggleOption(opt.label)">
          <view class="option-label">{{ opt.label }}</view>
          <text class="option-content">{{ opt.content }}</text>
        </view>
      </view>

      <!-- 主观题：文本输入 + 拍照上传 -->
      <view v-else class="subjective-area">
        <textarea v-model="textAnswer" placeholder="请输入答案" class="text-input" />

        <!-- 拍照上传 -->
        <view class="photo-section">
          <view class="photo-header">
            <text class="photo-label">拍照上传答案</text>
            <!-- H5 桌面端提示 -->
            <!-- #ifdef H5 -->
            <text v-if="!cameraSupported" class="photo-hint">请使用手机访问以使用拍照功能</text>
            <!-- #endif -->
          </view>

          <!-- 拍照按钮 + 缩略图 -->
          <view class="photo-grid">
            <!-- 已上传图片缩略图 -->
            <view v-for="(img, idx) in uploadedImages" :key="idx" class="thumb-item">
              <image :src="img.previewUrl" mode="aspectFill" class="thumb-image" @click="previewImage(idx)" />
              <view class="thumb-delete" @click="removeImage(idx)">
                <text class="delete-icon">×</text>
              </view>
            </view>

            <!-- 拍照按钮（圆形相机） -->
            <view v-if="canAddPhoto" @click="handleTakePhoto" class="camera-btn">
              <text class="camera-icon">&#128247;</text>
            </view>
          </view>
        </view>
      </view>

      <button class="submit-btn" @click="submitAnswer" :disabled="submitting">
        {{ submitting ? '提交中...' : '提交答案' }}
      </button>
    </view>
    <!-- 右侧反馈区 -->
    <view class="feedback-panel">
      <view v-if="feedback" class="feedback-card" :class="feedbackType">
        <view class="feedback-header">
          <text class="feedback-icon">{{ feedbackType === 'correct' ? '✅' : '❌' }}</text>
          <text class="feedback-title">{{ feedbackType === 'correct' ? '回答正确' : '回答错误' }}</text>
        </view>
        <text class="feedback-text">{{ feedback }}</text>
        <view class="feedback-actions">
          <button v-if="suggestGuidance" @click="startGuidance" class="btn-guidance">进入引导模式</button>
          <button v-else @click="nextQuestion" class="btn-next">{{ hasNext ? '下一题' : '完成' }}</button>
        </view>
      </view>
      <view v-else class="feedback-placeholder">
        <text>提交答案后显示反馈</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { studentApi } from '@/api/student.ts'
import { chooseImage, uploadImage, checkCameraSupport } from '@/utils/image-upload'

const levelId = ref(0)
const questions = ref<any[]>([])
const currentIndex = ref(0)
const selectedOptions = ref<string[]>([])
const textAnswer = ref('')
const feedback = ref('')
const feedbackType = ref('')
const suggestGuidance = ref(false)
const submitting = ref(false)

// 拍照上传相关
const uploadedImages = ref<Array<{ previewUrl: string; serverUrl: string }>>([])
const uploadingPhoto = ref(false)
const cameraSupported = ref(true) // #ifdef H5
// #ifdef H5
const camCheck = checkCameraSupport()
cameraSupported.value = camCheck.supported
// #endif

const currentQuestion = computed(() => questions.value[currentIndex.value] || {})
const isObjective = computed(() =>
  ['single_choice', 'multiple_choice'].includes(currentQuestion.value.question_type)
)
const hasNext = computed(() => currentIndex.value < questions.value.length - 1)
const canAddPhoto = computed(() => uploadedImages.value.length < 3 && !uploadingPhoto.value)

onMounted(async () => {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1] as any
  levelId.value = parseInt(page.options.levelId || '0')

  if (!levelId.value) {
    uni.showToast({ title: '缺少关卡ID', icon: 'none' })
    return
  }

  try {
    const res = await studentApi.levelDetail(levelId.value)
    questions.value = res.data?.questions || []
  } catch (e) {
    uni.showToast({ title: '加载题目失败', icon: 'none' })
  }
})

// ---------------------------------------------------------------------------
// 拍照上传
// ---------------------------------------------------------------------------

async function handleTakePhoto() {
  // #ifdef H5
  if (!cameraSupported.value) {
    uni.showToast({ title: '请使用手机访问以使用拍照功能', icon: 'none' })
    return
  }
  // #endif

  try {
    const results = await chooseImage({ count: 1, sourceType: ['camera', 'album'] })
    if (!results || results.length === 0) return

    uploadingPhoto.value = true
    uni.showLoading({ title: '上传中...' })

    const img = results[0]
    const baseUrl = (process.env.VUE_APP_BASE_URL as string) || ''
    const uploadUrl = `${baseUrl}/api/v1/questions/upload-image/`

    const uploadResult = await uploadImage({
      filePath: img.path,
      uploadUrl,
      fieldName: 'image',
      file: img.file,
    } as any)

    if (uploadResult.statusCode === 200 && uploadResult.data?.success) {
      const serverUrl = uploadResult.data.url || uploadResult.data.image_url || img.path
      uploadedImages.value.push({ previewUrl: img.path, serverUrl })
      uni.showToast({ title: '上传成功', icon: 'success' })
    } else {
      uni.showToast({ title: '上传失败', icon: 'none' })
    }
  } catch (e: any) {
    console.error('拍照上传失败:', e)
    uni.showToast({ title: '上传失败: ' + (e.message || ''), icon: 'none' })
  } finally {
    uploadingPhoto.value = false
    uni.hideLoading()
  }
}

function removeImage(idx: number) {
  uni.showModal({
    title: '确认删除',
    content: '确定要删除这张图片吗？',
    success: (res) => {
      if (res.confirm) {
        uploadedImages.value.splice(idx, 1)
      }
    },
  })
}

function previewImage(idx: number) {
  const urls = uploadedImages.value.map((img) => img.previewUrl)
  uni.previewImage({ current: urls[idx], urls })
}

function toggleOption(label: string) {
  const idx = selectedOptions.value.indexOf(label)
  if (idx >= 0) selectedOptions.value.splice(idx, 1)
  else selectedOptions.value.push(label)
}

async function submitAnswer() {
  submitting.value = true
  const content = isObjective.value
    ? { selected_options: selectedOptions.value }
    : { text: textAnswer.value, images: uploadedImages.value.map(img => img.serverUrl) }

  try {
    const res = await studentApi.submitAnswer({
      question_id: currentQuestion.value.id,
      answer_content: content,
      level_id: levelId.value,
    })
    feedback.value = res.data?.feedback || ''
    feedbackType.value = res.data?.is_correct ? 'correct' : 'incorrect'
    suggestGuidance.value = res.data?.suggest_guidance || false
  } catch (e) {
    uni.showToast({ title: '提交失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function startGuidance() {
  uni.navigateTo({
    url: `/pages/student/guidance?questionId=${currentQuestion.value.id}&levelId=${levelId.value}`,
  })
}

function nextQuestion() {
  feedback.value = ''
  feedbackType.value = ''
  suggestGuidance.value = false
  if (hasNext.value) {
    currentIndex.value++
    selectedOptions.value = []
    textAnswer.value = ''
    uploadedImages.value = []
  } else {
    uni.navigateBack()
  }
}
</script>

<style scoped>
.answer-page {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.question-panel {
  flex: 1;
  padding: 30rpx 40rpx;
}
.question-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 30rpx;
}
.q-no {
  font-size: 24rpx;
  color: #999;
}
.q-type {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}
.options-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16rpx;
  margin-bottom: 30rpx;
}
.option-card {
  border: 2rpx solid #ddd;
  border-radius: 12rpx;
  padding: 24rpx;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.2s, background 0.2s;
}
.option-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
}
.option-label {
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  background: #eee;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
  font-weight: bold;
  margin-bottom: 12rpx;
}
.option-card.selected .option-label {
  background: #409eff;
  color: #fff;
}
.option-content {
  font-size: 26rpx;
  color: #333;
}
.subjective-area {
  margin-bottom: 30rpx;
}
.text-input {
  width: 100%;
  min-height: 300rpx;
  border: 1rpx solid #ddd;
  border-radius: 12rpx;
  padding: 20rpx;
  box-sizing: border-box;
  background: #fff;
  font-size: 26rpx;
}

/* 拍照上传区域 */
.photo-section {
  margin-top: 24rpx;
}
.photo-header {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 16rpx;
}
.photo-label {
  font-size: 24rpx;
  color: #666;
  font-weight: 500;
}
.photo-hint {
  font-size: 20rpx;
  color: #999;
}
.photo-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  align-items: center;
}

/* 缩略图 */
.thumb-item {
  position: relative;
  width: 160rpx;
  height: 160rpx;
  border-radius: 12rpx;
  overflow: hidden;
  border: 1rpx solid #eee;
}
.thumb-image {
  width: 100%;
  height: 100%;
}
.thumb-delete {
  position: absolute;
  top: 0;
  right: 0;
  width: 40rpx;
  height: 40rpx;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 0 0 0 12rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.delete-icon {
  color: #fff;
  font-size: 24rpx;
  line-height: 1;
}

/* 拍照按钮（圆形） */
.camera-btn {
  width: 160rpx;
  height: 160rpx;
  border-radius: 50%;
  background: #409eff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4rpx 12rpx rgba(64, 158, 255, 0.3);
  transition: transform 0.15s, box-shadow 0.15s;
}
.camera-btn:active {
  transform: scale(0.95);
  box-shadow: 0 2rpx 6rpx rgba(64, 158, 255, 0.2);
}
.camera-icon {
  font-size: 48rpx;
  line-height: 1;
}
.submit-btn {
  background: #409eff;
  color: #fff;
  font-size: 28rpx;
  padding: 20rpx 0;
  border-radius: 8rpx;
}
.submit-btn[disabled] {
  background: #ccc;
}
.feedback-panel {
  width: 340px;
  padding: 30rpx 24rpx;
  background: #fff;
  border-left: 1rpx solid #e8e8e8;
  display: flex;
  align-items: center;
}
.feedback-card {
  padding: 30rpx;
  border-radius: 12rpx;
  width: 100%;
}
.feedback-card.correct {
  background: #e8f5e9;
}
.feedback-card.incorrect {
  background: #fff3e0;
}
.feedback-header {
  display: flex;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 16rpx;
}
.feedback-icon {
  font-size: 32rpx;
}
.feedback-title {
  font-size: 28rpx;
  font-weight: bold;
}
.feedback-text {
  font-size: 24rpx;
  color: #333;
  display: block;
  margin-bottom: 20rpx;
  line-height: 1.6;
}
.feedback-actions {
  display: flex;
  gap: 12rpx;
}
.btn-guidance {
  flex: 1;
  background: #409eff;
  color: #fff;
  font-size: 24rpx;
}
.btn-next {
  flex: 1;
  background: #4caf50;
  color: #fff;
  font-size: 24rpx;
}
.feedback-placeholder {
  text-align: center;
  color: #ccc;
  font-size: 26rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .answer-page {
    flex-direction: column;
  }
  .feedback-panel {
    width: 100%;
    min-height: 200px;
    border-left: none;
    border-top: 1rpx solid #e8e8e8;
    padding: 20rpx;
  }
  .options-grid {
    grid-template-columns: 1fr;
  }
}
</style>
