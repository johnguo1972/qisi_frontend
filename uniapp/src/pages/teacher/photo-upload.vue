<template>
  <view class="container">
    <view class="header">
      <text class="title">拍照新增试题</text>
      <text class="hint">对试题进行拍照，可连续拍多张</text>
    </view>

    <!-- Action buttons -->
    <view class="actions">
      <button class="btn-camera" @click="takePhoto">📷 拍照</button>
      <button class="btn-upload" @click="uploadFromAlbum">📁 从相册选择</button>
    </view>

    <!-- Photo list -->
    <view v-if="photos.length > 0" class="photo-list">
      <text class="section-label">已拍照片 ({{ photos.length }})</text>
      <view class="photo-grid">
        <view v-for="(photo, idx) in photos" :key="idx" class="photo-item">
          <image :src="photo.path" mode="aspectFit" class="photo-thumb" />
          <text class="photo-index">{{ idx + 1 }}</text>
          <view class="photo-delete" @click="deletePhoto(idx)">✕</view>
        </view>
      </view>
    </view>

    <!-- Submit bar -->
    <view class="submit-bar">
      <button class="btn-cancel" @click="goBack">取消</button>
      <button class="btn-submit" :disabled="photos.length === 0 || submitting" @click="handleRecognize">
        {{ submitting ? '识别中...' : '开始识别 (' + photos.length + '张)' }}
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useUserStore } from '@/store/index.ts'

interface Photo {
  path: string
  file?: File
}

const photos = ref<Photo[]>([])
const submitting = ref(false)
const userStore = useUserStore()

function goBack() { uni.navigateBack() }

function takePhoto() {
  // #ifdef H5
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.capture = 'environment'
  input.multiple = true
  input.onchange = (e: Event) => {
    const files = (e.target as HTMLInputElement).files
    if (files) {
      for (const f of Array.from(files)) {
        photos.value.push({ path: URL.createObjectURL(f), file: f as File })
      }
    }
  }
  input.click()
  // #endif
  // #ifndef H5
  uni.chooseMedia({
    count: 9,
    mediaType: ['image'],
    sourceType: ['camera'],
    success: (res) => {
      for (const item of res.tempFiles) {
        photos.value.push({ path: item.tempFilePath })
      }
    }
  })
  // #endif
}

function uploadFromAlbum() {
  // #ifdef H5
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.multiple = true
  input.onchange = (e: Event) => {
    const files = (e.target as HTMLInputElement).files
    if (files) {
      for (const f of Array.from(files)) {
        photos.value.push({ path: URL.createObjectURL(f), file: f as File })
      }
    }
  }
  input.click()
  // #endif
  // #ifndef H5
  uni.chooseMedia({
    count: 9,
    mediaType: ['image'],
    sourceType: ['album'],
    success: (res) => {
      for (const item of res.tempFiles) {
        photos.value.push({ path: item.tempFilePath })
      }
    }
  })
  // #endif
}

function deletePhoto(idx: number) {
  photos.value.splice(idx, 1)
}

async function handleRecognize() {
  if (photos.value.length === 0) return
  submitting.value = true
  try {
    // #ifdef H5
    const formData = new FormData()
    for (const photo of photos.value) {
      if (photo.file) {
        formData.append('images', photo.file)
      }
    }
    const token = uni.getStorageSync('accessToken') || ''
    const resp = await fetch('/study/api/v1/questions/photo-create/', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + token },
      body: formData,
    })
    const res = await resp.json()
    // #endif
    // #ifndef H5
    const paths = photos.value.map(p => p.path)
    const token = uni.getStorageSync('accessToken') || ''
    // APP 端逐个上传图片，确保每张都用 name: 'images' 字段名
    let lastRes: any = null
    for (const p of paths) {
      lastRes = await new Promise((resolve, reject) => {
        uni.uploadFile({
          url: 'https://qisi.chengxuelu.com/study/api/v1/questions/photo-create/',
          filePath: p,
          name: 'images',
          header: { 'Authorization': 'Bearer ' + token },
          success: (r) => {
            try { resolve(JSON.parse(r.data)) } catch { reject(new Error('Parse error')) }
          },
          fail: reject,
        })
      })
    }
    const res = lastRes
    // #endif

    if (res.code === 0) {
      uni.showToast({ title: '识别成功', icon: 'success' })
      const qid = res.data?.question_id
      if (qid) {
        uni.redirectTo({ url: `/pages/teacher/question-edit?id=${qid}` })
      } else {
        uni.navigateBack()
      }
    } else if (res.id) {
      // 接口返回的是扁平数据（直接返回题目对象）
      uni.showToast({ title: '识别成功', icon: 'success' })
      uni.redirectTo({ url: `/pages/teacher/question-edit?id=${res.id}` })
    } else {
      uni.showToast({ title: res.message || '识别失败', icon: 'none' })
    }
  } catch (e: any) {
    console.error('识别失败:', e)
    uni.showToast({ title: e?.message || '识别失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.container { padding: 24px; background: #f5f7fa; min-height: 100vh; }
.header { margin-bottom: 24px; }
.title { font-size: 18px; font-weight: 500; color: #303133; display: block; }
.hint { font-size: 13px; color: #909399; margin-top: 4px; display: block; }
.actions { display: flex; gap: 12px; margin-bottom: 24px; }
.btn-camera { flex: 1; background: #409eff; color: #fff; border: none; border-radius: 8px; padding: 14px; font-size: 15px; }
.btn-upload { flex: 1; background: #fff; color: #409eff; border: 1px solid #409eff; border-radius: 8px; padding: 14px; font-size: 15px; }
.photo-list { margin-bottom: 24px; }
.section-label { font-size: 14px; color: #606266; margin-bottom: 12px; display: block; }
.photo-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.photo-item { position: relative; aspect-ratio: 1; border-radius: 8px; overflow: hidden; background: #f0f0f0; }
.photo-thumb { width: 100%; height: 100%; }
.photo-index { position: absolute; top: 4px; left: 4px; background: rgba(0,0,0,0.5); color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 4px; }
.photo-delete { position: absolute; top: 4px; right: 4px; background: rgba(245,108,108,0.8); color: #fff; font-size: 12px; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.submit-bar { display: flex; gap: 12px; position: fixed; bottom: 0; left: 0; right: 0; padding: 12px 24px; background: #fff; border-top: 1px solid #ebeef5; }
.btn-cancel { flex: 1; background: #fff; color: #606266; border: 1px solid #dcdfe6; border-radius: 8px; padding: 12px; font-size: 14px; }
.btn-submit { flex: 2; background: #409eff; color: #fff; border: none; border-radius: 8px; padding: 12px; font-size: 14px; }
.btn-submit:disabled { background: #a0cfff; }
</style>
