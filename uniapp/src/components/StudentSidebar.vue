<template>
  <view class="sidebar">
    <view class="sidebar-logo" @click="goHome">A自习室</view>
    <view class="sidebar-user">
      <view class="user-info-row">
        <text class="user-name">{{ userInfo.display_name || '同学' }}</text>
        <view class="edit-btn" @click="showEditDialog">
          <text class="edit-icon">✎</text>
        </view>
      </view>
      <text class="user-role">学生{{ gradeLabel ? ' · ' + gradeLabel : '' }}</text>
    </view>
    <view class="nav-items">
      <view class="nav-item" :class="{ active: activeItem === 'home' }" @click="goHome">
        <text class="nav-icon">&#128203;</text>
        <text class="nav-text">首页</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'wrongbook' }" @click="goWrongBook">
        <text class="nav-icon">&#10060;</text>
        <text class="nav-text">错题本</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'knowledge' }" @click="goKnowledgeGraph">
        <text class="nav-icon">&#127757;</text>
        <text class="nav-text">知识图谱</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'growth' }" @click="goGrowth">
        <text class="nav-icon">&#128200;</text>
        <text class="nav-text">成长</text>
      </view>
      <view class="nav-item" :class="{ active: activeItem === 'join-class' }" @click="goJoinClass">
        <text class="nav-icon">&#128101;</text>
        <text class="nav-text">加入班级</text>
      </view>
      <view class="nav-item nav-logout" @click="handleLogout">
        <text class="nav-icon">&#128682;</text>
        <text class="nav-text">退出登录</text>
      </view>
    </view>

    <!-- 编辑资料弹窗 -->
    <view v-if="dialogVisible" class="dialog-overlay" @click="closeDialog">
      <view class="dialog" @click.stop>
        <view class="dialog-header">
          <text class="dialog-title">编辑个人资料</text>
          <text class="dialog-close" @click="closeDialog">×</text>
        </view>
        <view class="dialog-body">
          <view class="form-item">
            <text class="form-label">昵称</text>
            <input class="form-input" v-model="form.display_name" placeholder="请输入昵称" maxlength="20" />
          </view>
          <view class="form-item">
            <text class="form-label">目前年级</text>
            <select class="form-select" v-model="form.grade_level">
              <option value="" disabled>请选择年级</option>
              <option v-for="(g, i) in GRADE_OPTIONS" :key="i" :value="g">{{ g }}</option>
            </select>
          </view>
        </view>
        <view class="dialog-footer">
          <view class="btn btn-cancel" @click="closeDialog">
            <text>取消</text>
          </view>
          <view class="btn btn-save" @click="handleSave">
            <text>保存</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { authApi } from '@/api/index.ts'
import { useUserStore } from '@/store/index.ts'

const props = defineProps<{
  activeItem: string
}>()

const emit = defineEmits(['navigate'])

const userInfo = ref({ display_name: '同学', grade_level: null as string | null })
const userStore = useUserStore()

// 年级选项
const GRADE_OPTIONS = [
  '一年级', '二年级', '三年级', '四年级', '五年级', '六年级',
  '七年级', '八年级', '九年级',
  '高一', '高二', '高三'
]

const gradeLabel = computed(() => {
  // 弹窗打开时用 form 的值，关闭后用 userInfo 的值
  return dialogVisible.value
    ? (form.value.grade_level || '')
    : (userInfo.value.grade_level || '')
})

// 表单数据
const form = ref({ display_name: '', grade_level: '' as string | null })
const dialogVisible = ref(false)

onMounted(async () => {
  try {
    const profile = await authApi.getProfile()
    if (profile.data) {
      userInfo.value = profile.data
      // 同步更新 userStore
      userStore.setUserInfo(profile.data)
    }
  } catch {}
})

function goHome() { emit('navigate', 'home') }
function goWrongBook() { emit('navigate', 'wrongbook') }
function goKnowledgeGraph() { uni.navigateTo({ url: '/pages/student/knowledge-graph' }) }
function goGrowth() { emit('navigate', 'growth') }
function goJoinClass() { emit('navigate', 'join-class') }

async function handleLogout() {
  uni.showModal({
    title: '确认退出',
    content: '确定要退出登录吗？',
    success: async (res) => {
      if (res.confirm) {
        try { await authApi.logout() } catch {}
        userStore.logout()
        uni.reLaunch({ url: '/pages/login/index' })
      }
    },
  })
}

// 弹窗操作
function showEditDialog() {
  form.value = {
    display_name: userInfo.value.display_name || '',
    grade_level: userInfo.value.grade_level || '',
  }
  dialogVisible.value = true
}

function closeDialog() {
  dialogVisible.value = false
}

async function handleSave() {
  if (!form.value.display_name.trim()) {
    uni.showToast({ title: '昵称不能为空', icon: 'none' })
    return
  }
  try {
    const res = await authApi.updateProfile({
      display_name: form.value.display_name.trim(),
      grade_level: form.value.grade_level,
    })
    if (res.code === 0 && res.data) {
      userInfo.value = res.data
      userStore.setUserInfo(res.data)
      uni.showToast({ title: '保存成功', icon: 'success' })
      closeDialog()
    } else {
      uni.showToast({ title: res.message || '保存失败', icon: 'none' })
    }
  } catch (e) {
    console.error('保存失败:', e)
    uni.showToast({ title: '网络错误，请重试', icon: 'none' })
  }
}
</script>

<style scoped>
.sidebar {
  width: 240px;
  background: #fff;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 10;
}
.sidebar-logo {
  padding: 30rpx 24rpx;
  font-size: 32rpx;
  font-weight: bold;
  color: #409eff;
  border-bottom: 1rpx solid #f0f0f0;
  cursor: pointer;
}
.sidebar-user {
  padding: 24rpx;
  border-bottom: 1rpx solid #f0f0f0;
}
.user-info-row {
  display: flex;
  align-items: center;
  gap: 8rpx;
}
.user-name {
  font-size: 26rpx;
  font-weight: bold;
  color: #333;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.edit-btn {
  flex-shrink: 0;
  width: 36rpx;
  height: 36rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 50%;
  transition: background 0.2s;
}
.edit-btn:hover {
  background: #f0f0f0;
}
.edit-icon {
  font-size: 22rpx;
  color: #999;
}
.user-role {
  font-size: 22rpx;
  color: #999;
  margin-top: 4rpx;
  display: block;
}
.nav-items {
  padding: 16rpx 0;
  flex: 1;
  overflow-y: auto;
}
.nav-item {
  display: flex;
  align-items: center;
  padding: 16rpx 24rpx;
  cursor: pointer;
  transition: background 0.2s;
}
.nav-item:hover {
  background: #f5f5f5;
}
.nav-item.active {
  background: #ecf5ff;
  color: #409eff;
}
.nav-icon {
  font-size: 32rpx;
  margin-right: 12rpx;
}
.nav-text {
  font-size: 26rpx;
  color: #333;
}
.nav-item.active .nav-text {
  color: #409eff;
}
.nav-logout {
  margin-top: auto;
}
.nav-logout:hover {
  background: #fff0f0;
}
.nav-logout .nav-icon {
  opacity: 0.7;
}
.nav-logout .nav-text {
  color: #e74c3c;
}

/* 弹窗样式 */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.dialog {
  width: 600rpx;
  background: #fff;
  border-radius: 16rpx;
  overflow: hidden;
}
.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32rpx 40rpx 24rpx;
  border-bottom: 1rpx solid #f0f0f0;
}
.dialog-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
}
.dialog-close {
  font-size: 40rpx;
  color: #999;
  cursor: pointer;
  line-height: 1;
  padding: 0 8rpx;
}
.dialog-close:hover {
  color: #333;
}
.dialog-body {
  padding: 32rpx 40rpx;
}
.form-item {
  margin-bottom: 32rpx;
}
.form-item:last-child {
  margin-bottom: 0;
}
.form-label {
  font-size: 26rpx;
  color: #666;
  margin-bottom: 12rpx;
  display: block;
}
.form-input {
  width: 100%;
  height: 72rpx;
  padding: 0 20rpx;
  border: 1rpx solid #e0e0e0;
  border-radius: 8rpx;
  font-size: 28rpx;
  color: #333;
  box-sizing: border-box;
}
.form-input:focus {
  border-color: #409eff;
}
.form-select {
  width: 100%;
  height: 72rpx;
  padding: 0 20rpx;
  border: 1rpx solid #e0e0e0;
  border-radius: 8rpx;
  font-size: 28rpx;
  color: #333;
  background: #fff;
  box-sizing: border-box;
}
.form-select:focus {
  border-color: #409eff;
  outline: none;
}
.dialog-footer {
  display: flex;
  gap: 16rpx;
  padding: 24rpx 40rpx 32rpx;
}
.btn {
  flex: 1;
  height: 72rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8rpx;
  font-size: 28rpx;
  cursor: pointer;
  transition: opacity 0.2s;
}
.btn:hover {
  opacity: 0.85;
}
.btn-cancel {
  background: #f5f5f5;
  color: #666;
}
.btn-save {
  background: #409eff;
  color: #fff;
}
</style>
