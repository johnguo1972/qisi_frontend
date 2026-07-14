<template>
  <view class="answer-page">
    <view class="question-panel">
      <view class="question-header">
        <text class="q-no">同类题 {{ currentIndex + 1 }}/{{ questions.length }}</text>
        <text class="q-type">{{ typeLabel(currentQuestion.question_type) }}</text>
      </view>

      <view v-if="currentQuestion.stem" class="stem">{{ currentQuestion.stem }}</view>
      <image v-for="(img,i) in (currentQuestion.images||[])" :key="i"
             :src="img.url" class="stem-img" mode="widthFix" />

      <view v-if="isObjective" class="options-grid">
        <view v-for="opt in (currentQuestion.options||[])" :key="opt.label"
              class="option-card" :class="{ selected: selectedOptions.includes(opt.label) }"
              @click="toggleOption(opt.label)">
          <view class="option-label">{{ opt.label }}</view>
          <text class="option-content">{{ opt.content }}</text>
        </view>
      </view>
      <view v-else class="subjective-area">
        <textarea v-model="textAnswer" placeholder="请输入答案" class="text-input" />
      </view>

      <button class="submit-btn" @click="submit" :disabled="submitting">
        {{ submitting ? '提交中...' : '提交' }}
      </button>
    </view>

    <view class="feedback-panel">
      <view v-if="feedback" class="feedback-card" :class="feedbackType">
        <text class="feedback-title">
          {{ feedbackType === 'correct' ? '✅ 正确' : (feedbackType === 'pending' ? '⏳ 待批阅' : '❌ 不正确') }}
        </text>
        <text class="feedback-text">{{ feedback }}</text>
        <button v-if="!submitting" class="btn-next" @click="next">
          {{ hasNext ? '下一题' : '完成' }}
        </button>
      </view>
      <view v-else class="feedback-placeholder"><text>提交后显示结果</text></view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { wrongbookApi } from '@/api/student.ts'

interface Opt { label: string; content: string }
interface Q { id: number; question_type: string; stem?: string; options?: Opt[]; images?: { url: string }[] }

const itemId = ref(0)
const questions = ref<Q[]>([])
const currentIndex = ref(0)
const selectedOptions = ref<string[]>([])
const textAnswer = ref('')
const feedback = ref('')
const feedbackType = ref('')
const submitting = ref(false)

const currentQuestion = computed(() => questions.value[currentIndex.value] || ({} as Q))
const isObjective = computed(() =>
  ['single_choice', 'multiple_choice'].includes(currentQuestion.value.question_type))
const hasNext = computed(() => currentIndex.value < questions.value.length - 1)

onLoad((options: any) => {
  itemId.value = parseInt(options?.itemId || '0')
})

onMounted(async () => {
  if (!itemId.value) { uni.showToast({ title: '缺少错题ID', icon: 'none' }); return }
  try {
    const res = await wrongbookApi.variants(itemId.value)
    questions.value = res.data || []
    if (!questions.value.length) uni.showToast({ title: '暂无同类题', icon: 'none' })
  } catch { uni.showToast({ title: '加载失败', icon: 'none' }) }
})

function toggleOption(label: string) {
  if (currentQuestion.value.question_type === 'single_choice') {
    selectedOptions.value = selectedOptions.value.includes(label) ? [] : [label]
  } else {
    const i = selectedOptions.value.indexOf(label)
    if (i >= 0) {
      selectedOptions.value.splice(i, 1)
    } else {
      selectedOptions.value.push(label)
    }
  }
}

async function submit() {
  if (!currentQuestion.value.id) return
  submitting.value = true
  const answer_content = isObjective.value
    ? { selected_options: selectedOptions.value }
    : { text: textAnswer.value }
  try {
    const res = await wrongbookApi.variantSubmit(itemId.value, {
      question_id: currentQuestion.value.id, answer_content,
    })
    feedback.value = res.data?.feedback || ''
    feedbackType.value = res.data?.is_pending ? 'pending'
      : (res.data?.is_correct ? 'correct' : 'incorrect')
  } catch { uni.showToast({ title: '提交失败', icon: 'none' }) }
  finally { submitting.value = false }
}

function next() {
  feedback.value = ''; feedbackType.value = ''
  selectedOptions.value = []; textAnswer.value = ''
  if (hasNext.value) currentIndex.value++
  else uni.navigateBack()
}

function typeLabel(t: string) {
  return ({ single_choice: '单选', multiple_choice: '多选', fill_blank: '填空',
    short_answer: '简答', essay: '论述', computation: '计算', proof: '证明',
    true_false: '判断' } as Record<string, string>)[t] || t
}
</script>

<style scoped>
.answer-page { display:flex; min-height:100vh; background:#f0f2f5; }
.question-panel { flex:1; padding:30rpx 40rpx; }
.question-header { display:flex; justify-content:space-between; margin-bottom:20rpx; }
.q-no { font-size:24rpx; color:#999; }
.q-type { font-size:28rpx; font-weight:bold; color:#333; }
.stem { font-size:28rpx; color:#333; line-height:1.6; margin-bottom:16rpx; }
.stem-img { width:100%; border-radius:8rpx; margin-bottom:16rpx; }
.options-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:16rpx; margin-bottom:30rpx; }
.option-card { border:2rpx solid #ddd; border-radius:12rpx; padding:24rpx; background:#fff; }
.option-card.selected { border-color:#409eff; background:#ecf5ff; }
.option-label { width:40rpx;height:40rpx;border-radius:50%;background:#eee;
  display:flex;align-items:center;justify-content:center;font-size:22rpx;font-weight:bold;margin-bottom:12rpx; }
.option-card.selected .option-label { background:#409eff;color:#fff; }
.option-content { font-size:26rpx;color:#333; }
.subjective-area { margin-bottom:30rpx; }
.text-input { width:100%;min-height:300rpx;border:1rpx solid #ddd;border-radius:12rpx;
  padding:20rpx;box-sizing:border-box;background:#fff;font-size:26rpx; }
.submit-btn { background:#409eff;color:#fff;font-size:28rpx;padding:20rpx 0;border-radius:8rpx; }
.submit-btn[disabled]{background:#ccc;}
.feedback-panel { width:340px;padding:30rpx 24rpx;background:#fff;border-left:1rpx solid #e8e8e8;display:flex;align-items:center; }
.feedback-card { padding:30rpx;border-radius:12rpx;width:100%; }
.feedback-card.correct{background:#e8f5e9;} .feedback-card.incorrect{background:#fff3e0;} .feedback-card.pending{background:#eef6ff;}
.feedback-title{font-size:28rpx;font-weight:bold;display:block;margin-bottom:12rpx;}
.feedback-text{font-size:24rpx;color:#333;display:block;margin-bottom:20rpx;line-height:1.6;}
.btn-next{background:#4caf50;color:#fff;font-size:24rpx;}
.feedback-placeholder{text-align:center;color:#ccc;font-size:26rpx;}
@media (max-width:768px){ .answer-page{flex-direction:column;} .feedback-panel{width:100%;border-left:none;border-top:1rpx solid #e8e8e8;} .options-grid{grid-template-columns:1fr;} }
</style>
