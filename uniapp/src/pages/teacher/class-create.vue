<template>
  <view class="class-create">
    <TeacherSidebar activeItem="classes" />

    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">创建班级</text>
      </view>
      <view class="form-card">
        <view class="form-item">
          <text class="form-label">所属机构 <text class="required">*</text></text>
          <picker :range="institutionLabels" :value="institutionIndex" @change="form.institution_id = institutions[$event.detail.value].id; institutionIndex = $event.detail.value">
            <view class="picker-display">{{ institutionLabels[institutionIndex] || '请选择机构' }}</view>
          </picker>
        </view>
        <view class="form-item">
          <text class="form-label">班级名称 <text class="required">*</text></text>
          <input
            class="form-input"
            v-model="form.class_name"
            placeholder="请输入班级名称"
            maxlength="50"
          />
        </view>
        <view class="form-item">
          <text class="form-label">班级描述</text>
          <textarea
            class="form-textarea"
            v-model="form.description"
            placeholder="请输入班级描述（可选）"
            maxlength="200"
          />
        </view>
        <view class="form-item">
          <text class="form-label">最大学生数</text>
          <input
            class="form-input"
            v-model.number="form.max_students"
            type="number"
            placeholder="0 表示不限制"
          />
        </view>
        <view class="form-item form-checkbox-item">
          <label class="checkbox-label">
            <checkbox :checked="form.allow_invite_join" @change="toggleInvite" />
            <text class="checkbox-text">允许使用邀请码加入</text>
          </label>
        </view>
        <view class="form-actions">
          <button class="btn-cancel" @click="goBack">取消</button>
          <button class="btn-submit" :disabled="submitting" @click="handleSubmit">
            {{ submitting ? '提交中...' : '创建班级' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { classApi, teacherApi } from '@/api/index.ts'
import TeacherSidebar from '@/components/TeacherSidebar.vue'

interface CreateForm {
  institution_id: number
  class_name: string
  description: string
  max_students: number
  allow_invite_join: boolean
}

interface Institution {
  id: number
  institution_name: string
}

const submitting = ref(false)
const institutions = ref<Institution[]>([])
const institutionIndex = ref(0)

const institutionLabels = computed(() => institutions.value.map(i => i.institution_name))

const form = reactive<CreateForm>({
  institution_id: 0,
  class_name: '',
  description: '',
  max_students: 0,
  allow_invite_join: true,
})

onLoad(async () => {
  try {
    const res: any = await teacherApi.institutions()
    if (res.code === 0 && res.data && res.data.length > 0) {
      institutions.value = res.data
      form.institution_id = res.data[0].id
    } else {
      uni.showToast({ title: '您还不是任何机构的教师，请联系管理员', icon: 'none', duration: 4000 })
    }
  } catch (e) {
    console.error('Failed to load institutions:', e)
    uni.showToast({ title: '加载机构列表失败', icon: 'none' })
  }
})

function toggleInvite(e: any) {
  form.allow_invite_join = e.detail.value.length > 0
}

async function handleSubmit() {
  if (!form.institution_id) {
    uni.showToast({ title: '请选择所属机构', icon: 'none' })
    return
  }
  if (!form.class_name.trim()) {
    uni.showToast({ title: '请输入班级名称', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    const res: any = await classApi.create({
      institution_id: form.institution_id,
      class_name: form.class_name.trim(),
      description: form.description.trim() || undefined,
      max_students: form.max_students || 0,
      allow_invite_join: form.allow_invite_join,
    })
    if (res.code === 0) {
      uni.showToast({ title: '创建成功', icon: 'success' })
      const newClassId = res.data?.id
      if (newClassId) {
        setTimeout(() => {
          uni.redirectTo({ url: `/pages/teacher/class-detail?classId=${newClassId}` })
        }, 1000)
      } else {
        setTimeout(() => {
          uni.navigateBack()
        }, 1000)
      }
    } else {
      uni.showToast({ title: res.message || '创建失败', icon: 'none' })
    }
  } catch (e: any) {
    console.error('Failed to create class:', e)
    uni.showToast({ title: '创建失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function goBack() { uni.navigateBack() }
</script>

<style scoped>
.class-create {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 240px;
  flex: 1;
  padding: 30rpx 40rpx;
}
.page-header {
  padding: 10rpx 0 30rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.form-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 32rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
  max-width: 640px;
}
.form-item {
  margin-bottom: 24rpx;
}
.form-label {
  font-size: 26rpx;
  color: #333;
  font-weight: bold;
  display: block;
  margin-bottom: 12rpx;
}
.required {
  color: #e74c3c;
}
.form-input {
  width: 100%;
  height: 72rpx;
  border: 1rpx solid #dcdfe6;
  border-radius: 8rpx;
  padding: 0 20rpx;
  font-size: 26rpx;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.form-input:focus {
  border-color: #409eff;
}
.form-textarea {
  width: 100%;
  height: 160rpx;
  border: 1rpx solid #dcdfe6;
  border-radius: 8rpx;
  padding: 16rpx 20rpx;
  font-size: 26rpx;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.form-textarea:focus {
  border-color: #409eff;
}
.form-checkbox-item {
  display: flex;
  align-items: center;
}
.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
}
.checkbox-text {
  font-size: 26rpx;
  color: #333;
  margin-left: 12rpx;
}
.form-actions {
  display: flex;
  gap: 16rpx;
  margin-top: 32rpx;
  padding-top: 24rpx;
  border-top: 1rpx solid #f0f0f0;
}
.btn-cancel {
  background: #fff;
  color: #666;
  border: 1rpx solid #dcdfe6;
  border-radius: 8rpx;
  padding: 16rpx 48rpx;
  font-size: 26rpx;
  cursor: pointer;
}
.btn-submit {
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  padding: 16rpx 48rpx;
  font-size: 26rpx;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-submit:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}
.picker-display {
  padding: 14px 16px;
  background: #fafafa;
  border: 1rpx solid #dcdfe6;
  border-radius: 8rpx;
  font-size: 26rpx;
  color: #333;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .main { margin-left: 60px; padding: 20rpx; }
  .form-card { max-width: 100%; }
}
</style>