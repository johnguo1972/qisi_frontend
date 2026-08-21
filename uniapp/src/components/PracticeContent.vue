<template>
  <view class="content">
    <view class="header"><text class="title">精练题</text><text class="hint">从错题关联题中组建个人练习</text></view>

    <view v-if="!readonly" class="card">
      <view class="card-title">待组卷题目（{{ pool.length }}）</view>
      <view v-if="!pool.length" class="empty">暂无题目，请先从错题本选择“加入精练列表”</view>
      <view v-for="item in pool" :key="item.id" class="pool-row">
        <checkbox :checked="selected.includes(String(item.id))" @click="toggle(String(item.id))" />
        <view class="pool-body"><text class="meta">{{ sourceLabel(item.source_type) }} · {{ item.display_snapshot?.question_type_label || '题目' }}</text><text class="stem">{{ plain(item.display_snapshot?.stem || item.display_snapshot?.stem_html) }}</text></view>
        <button size="mini" class="remove" @click="removeItem(item.id)">移除</button>
      </view>
      <view class="compose"><input v-model="title" class="title-input" placeholder="精练作业标题" maxlength="60" /><button type="primary" size="mini" :disabled="creating" @click="createSet">{{ creating ? '组卷中...' : selected.length ? `组卷（${selected.length}）` : '请先选择题目' }}</button></view>
    </view>

    <view class="card"><view class="card-title">精练作业（{{ sets.length }}）</view>
      <view v-if="!sets.length" class="empty">暂无精练作业</view>
      <view v-for="item in sets" :key="item.id" class="set-row" @click="openSet(item.id)">
        <view class="set-main"><text class="set-title">{{ item.title }}</text><text class="meta">{{ statusLabel(item.status) }} · {{ item.question_count || 0 }} 题 · 已完成 {{ item.answered_count || 0 }} 题</text></view>
        <text class="progress">{{ Number(item.progress_percent || 0).toFixed(0) }}%</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { practiceApi } from '@/api/student'

const props = withDefaults(defineProps<{ readonly?: boolean }>(), { readonly: false })
const readonly = props.readonly
const pool = ref<any[]>([])
const sets = ref<any[]>([])
const selected = ref<string[]>([])
const title = ref('')
const creating = ref(false)

function plain(value: any) {
  return String(value || '暂无题干').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim() || '暂无题干'
}
function sourceLabel(value: string) { return value === 'original_wrong' ? '原错题' : value === 'recommended_variant' ? '关联题' : '手工题' }
function statusLabel(value: string) { return ({ draft: '草稿', active: '练习中', completed: '已完成', archived: '已归档' } as Record<string, string>)[value] || value }
function toggle(id: string) { const index = selected.value.indexOf(id); index >= 0 ? selected.value.splice(index, 1) : selected.value.push(id) }

async function load() {
  try {
    const [setResponse, poolResponse] = await Promise.all([
      practiceApi.sets(),
      readonly ? Promise.resolve({ data: [] }) : practiceApi.pool(),
    ])
    sets.value = (setResponse as any).data || []
    if (!readonly) pool.value = (poolResponse as any).data || []
  } catch { uni.showToast({ title: '精练数据加载失败', icon: 'none' }) }
}
async function removeItem(id: string) {
  const response: any = await practiceApi.removePoolItem(id)
  if (response.code === 0) { pool.value = pool.value.filter(item => String(item.id) !== String(id)); selected.value = selected.value.filter(item => item !== String(id)) }
}
async function createSet() {
  if (!selected.value.length) {
    uni.showToast({ title: '请先选择题目', icon: 'none' })
    return
  }
  creating.value = true
  try {
    const response: any = await practiceApi.createSet({ pool_item_ids: selected.value, title: title.value, status: 'active' })
    if (response.code !== 0) {
      uni.showToast({ title: response.message || '组卷失败', icon: 'none' })
      return
    }
    const createdId = String(response.data?.id || '')
    uni.showToast({ title: '组卷成功', icon: 'success' })
    selected.value = []; title.value = ''; await load()
    if (createdId) uni.navigateTo({ url: `/pages/student/practice-set-detail?id=${createdId}` })
  } finally { creating.value = false }
}
function openSet(id: string) {
  uni.navigateTo({
    url: `/pages/student/practice-set-detail?id=${id}${readonly ? '&readonly=1' : ''}`,
    fail: () => uni.showToast({ title: '打开精练作业失败', icon: 'none' }),
  })
}
onMounted(load)
</script>

<style scoped>
.content { width: 100%; box-sizing: border-box; }.header { margin-bottom: 20rpx; }.title { display: block; color: #303133; font-size: 36rpx; font-weight: 700; }.hint,.meta { display: block; margin-top: 8rpx; color: #909399; font-size: 22rpx; }.card { margin-bottom: 20rpx; padding: 24rpx; background: #fff; border-radius: 14rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.04); }.card-title { margin-bottom: 16rpx; color: #303133; font-size: 30rpx; font-weight: 600; }.pool-row,.set-row { display: flex; align-items: center; gap: 14rpx; padding: 18rpx 0; border-bottom: 1rpx solid #f0f0f0; }.pool-row:last-child,.set-row:last-child { border-bottom: 0; }.pool-body,.set-main { flex: 1; min-width: 0; }.stem,.set-title { display: block; overflow: hidden; color: #303133; font-size: 26rpx; line-height: 1.55; text-overflow: ellipsis; white-space: nowrap; }.set-title { font-weight: 600; }.remove { flex: none; color: #f56c6c; background: #fff1f0; }.compose { display: flex; gap: 14rpx; margin-top: 20rpx; }.title-input { flex: 1; height: 68rpx; padding: 0 16rpx; border: 1rpx solid #dcdfe6; border-radius: 8rpx; box-sizing: border-box; }.progress { flex: none; color: #409eff; font-size: 26rpx; }.empty { padding: 50rpx 10rpx; color: #909399; font-size: 24rpx; text-align: center; }
</style>
