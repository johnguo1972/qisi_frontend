<template>
  <view class="photo-upload">
    <view v-for="(image, index) in images" :key="index" class="thumb">
      <image :src="image.previewUrl" mode="aspectFill" @click="preview(index)" />
      <text class="remove" @click="remove(index)">×</text>
    </view>
    <view v-if="images.length < maxCount && !uploading" class="add" @click="choose">📷</view>
    <text v-if="uploading" class="status">上传中...</text>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { chooseAndUpload } from '@/utils/image-upload'
import { studentApi } from '@/api/student'

interface ImageItem { previewUrl: string; serverUrl: string }
const props = withDefaults(defineProps<{ images: ImageItem[]; attemptId: string; questionId: string; levelId?: string; maxCount?: number }>(), { maxCount: 3 })
const emit = defineEmits<{ 'update:images': [images: ImageItem[]]; 'attempt-created': [attemptId: string] }>()
const uploading = ref(false)

async function ensureAttempt() {
  if (props.attemptId) return props.attemptId
  const result: any = await studentApi.startAttempt({ question_id: props.questionId, level_id: props.levelId })
  if (result.code !== 0 || !result.data?.attempt_id) throw new Error(result.message || '无法创建作答记录')
  emit('attempt-created', result.data.attempt_id)
  return result.data.attempt_id
}

async function choose() {
  try {
    const attemptId = await ensureAttempt()
    uploading.value = true
    const urls = await chooseAndUpload({ count: props.maxCount - props.images.length, sourceType: ['camera', 'album'], attemptId })
    emit('update:images', [...props.images, ...urls.map(url => ({ previewUrl: url, serverUrl: url }))])
  } catch (error: any) {
    uni.showToast({ title: error.message || '图片上传失败', icon: 'none' })
  } finally { uploading.value = false }
}

function remove(index: number) {
  const next = props.images.slice(); next.splice(index, 1); emit('update:images', next)
}
function preview(index: number) { uni.previewImage({ current: props.images[index]?.previewUrl, urls: props.images.map(item => item.previewUrl) }) }
</script>

<style scoped>
.photo-upload { display: flex; flex-wrap: wrap; gap: 16rpx; }
.thumb, .add { position: relative; width: 150rpx; height: 150rpx; border-radius: 12rpx; overflow: hidden; background: #f5f5f5; }
.thumb image { width: 100%; height: 100%; }
.add { display: flex; align-items: center; justify-content: center; font-size: 44rpx; color: #409eff; }
.remove { position: absolute; top: 0; right: 0; width: 36rpx; height: 36rpx; text-align: center; line-height: 32rpx; border-radius: 50%; background: #e74c3c; color: #fff; }
.status { color: #409eff; font-size: 24rpx; align-self: center; }
</style>
