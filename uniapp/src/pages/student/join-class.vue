<template>
  <view class="join-class-page">
    <!-- 右侧内容区 -->
    <view class="main">
      <view class="tab-bar">
        <view :class="['tab-item', activeTab === 0 ? 'active' : '']" @click="activeTab = 0">
          <text>我的班级</text>
        </view>
        <view :class="['tab-item', activeTab === 1 ? 'active' : '']" @click="activeTab = 1">
          <text>搜索加入</text>
        </view>
        <view :class="['tab-item', activeTab === 2 ? 'active' : '']" @click="activeTab = 2">
          <text>邀请码</text>
        </view>
      </view>

      <!-- Tab 0: 我的班级 -->
      <view v-show="activeTab === 0" class="tab-content">
        <view v-if="myClasses.length > 0" class="my-classes-list">
          <view v-for="cls in myClasses" :key="cls.id" class="class-card">
            <view class="class-info">
              <text class="class-name">{{ cls.class_name }}</text>
              <text class="subject-text">{{ cls.subject || '未设置学科' }}</text>
              <text class="student-count">学生人数：{{ cls.student_count || 0 }}</text>
            </view>
            <button class="quit-btn" :disabled="quitting" @click="handleQuitClass(cls)">
              退出
            </button>
          </view>
        </view>
        <view v-else-if="!loadingMyClasses" class="empty-state">
          <text class="empty-icon">📚</text>
          <text class="empty-text">还没有加入任何班级</text>
          <text class="empty-hint">可以通过搜索手机号或邀请码加入班级</text>
        </view>
        <view v-else class="loading-state">
          <text>加载中...</text>
        </view>
      </view>

      <!-- Tab 1: 手机号搜索 -->
      <view v-show="activeTab === 1" class="tab-content">
        <view class="search-section">
          <input
            class="phone-input"
            type="number"
            maxlength="11"
            placeholder="请输入老师手机号"
            v-model="teacherPhone"
          />
          <button class="search-btn" :disabled="searching" @click="handleSearch">
            {{ searching ? '搜索中...' : '搜索班级' }}
          </button>
        </view>

        <view v-if="searchResults.length > 0" class="results-section">
          <text class="results-title">找到以下班级：</text>
          <view v-for="cls in searchResults" :key="cls.id" class="class-card">
            <view class="class-info">
              <text class="class-name">{{ cls.class_name }}</text>
              <text class="inst-name">{{ cls.institution_name }}</text>
              <text class="student-count">学生人数：{{ cls.student_count }}</text>
            </view>
            <button class="join-btn" :disabled="requesting" @click="handleRequestJoin(cls)">
              {{ requesting ? '申请中...' : '申请加入' }}
            </button>
          </view>
        </view>

        <view v-if="searched && searchResults.length === 0" class="empty-result">
          <text>未找到该老师开放的班级</text>
        </view>
      </view>

      <!-- Tab 2: 邀请码加入 -->
      <view v-show="activeTab === 2" class="tab-content">
        <view class="code-section">
          <text class="code-label">请输入8位班级邀请码</text>
          <input
            class="code-input"
            type="text"
            maxlength="8"
            placeholder="请输入邀请码"
            v-model="inviteCode"
          />
          <button class="code-submit-btn" :disabled="joining" @click="handleJoinByCode">
            {{ joining ? '加入中...' : '加入班级' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { studentClassApi, classApi } from '@/api/index.ts'
import { useUserStore } from '@/store/index.ts'

const userStore = useUserStore()

const activeTab = ref(0)

// Tab 0: 我的班级
const myClasses = ref<any[]>([])
const loadingMyClasses = ref(false)
const quitting = ref(false)

onMounted(async () => {
  await loadMyClasses()
})

async function loadMyClasses() {
  loadingMyClasses.value = true
  try {
    const res = await studentClassApi.myClasses()
    myClasses.value = res.data?.items || res.data || []
  } catch (e) {
    console.error('加载我的班级失败:', e)
  } finally {
    loadingMyClasses.value = false
  }
}

async function handleQuitClass(cls: any) {
  uni.showModal({
    title: '确认退出',
    content: `确定要退出班级"${cls.class_name}"吗？`,
    success: async (res) => {
      if (res.confirm) {
        quitting.value = true
        try {
          await classApi.quitClass(cls.id)
          uni.showToast({ title: '已退出班级', icon: 'success' })
          await loadMyClasses()
        } catch (e: any) {
          const msg = e?.data?.message || e?.data?.error || '退出失败，请重试'
          uni.showToast({ title: msg, icon: 'none' })
        } finally {
          quitting.value = false
        }
      }
    }
  })
}

// Tab 1
const teacherPhone = ref('')
const searching = ref(false)
const searched = ref(false)
const searchResults = ref<any[]>([])
const requesting = ref(false)

async function handleSearch() {
  if (!/^1\d{10}$/.test(teacherPhone.value)) {
    uni.showToast({ title: '请输入正确的手机号', icon: 'none' })
    return
  }
  searching.value = true
  searched.value = false
  try {
    const res = await studentClassApi.search(teacherPhone.value)
    searchResults.value = res.data?.classes || []
    searched.value = true
  } catch (e) {
    uni.showToast({ title: '搜索失败，请重试', icon: 'none' })
  } finally {
    searching.value = false
  }
}

async function handleRequestJoin(cls: any) {
  requesting.value = true
  try {
    await studentClassApi.submitJoinRequest({
      class_id: cls.id,
      request_type: 'phone_search',
      applicant_phone: teacherPhone.value,
    })
    uni.showToast({ title: '申请已提交，等待老师审批', icon: 'success' })
    activeTab.value = 0
    await loadMyClasses()
  } catch (e) {
    uni.showToast({ title: '申请失败，请重试', icon: 'none' })
  } finally {
    requesting.value = false
  }
}

// Tab 2
const inviteCode = ref('')
const joining = ref(false)

async function handleJoinByCode() {
  if (inviteCode.value.trim().length !== 8) {
    uni.showToast({ title: '请输入8位邀请码', icon: 'none' })
    return
  }
  joining.value = true
  try {
    // 如果用户没有 display_name，用手机号作为默认名
    let applicantName = userStore.userInfo?.display_name || ''
    if (!applicantName) {
      applicantName = userStore.userInfo?.mobile || userStore.userInfo?.phone || '学生用户'
    }
    console.log('[joinByCode] 请求参数:', { invite_code: inviteCode.value, applicant_name: applicantName })
    const res = await studentClassApi.joinByCode({
      invite_code: inviteCode.value.trim().toUpperCase(),
      applicant_name: applicantName,
    })
    const className = res.data?.class_name || '班级'
    uni.showToast({ title: `成功加入${className}`, icon: 'success' })
    activeTab.value = 0
    await loadMyClasses()
  } catch (e: any) {
    console.error('[joinByCode] 请求失败:', e)
    const data = e?.data
    if (data && typeof data === 'object') {
      const firstField = Object.keys(data)[0]
      const firstMsg = data[firstField]
      let msg = Array.isArray(firstMsg) ? firstMsg[0] : firstMsg

      // 将英文错误转为中文
      const errorMap: Record<string, string> = {
        'Invalid invite code': '邀请码无效，请检查后重试',
        'This class does not allow invite code joining': '该班级暂不支持邀请码加入',
        'This class has reached its maximum student capacity': '该班级已满，无法加入',
        'You are already a member of this class': '你已经是该班级成员',
      }
      msg = errorMap[msg] || msg || '加入失败，请重试'
      uni.showToast({ title: msg, icon: 'none' })
    } else {
      const msg = e?.data?.message || e?.data?.error || '邀请码无效或已过期'
      uni.showToast({ title: msg, icon: 'none' })
    }
  } finally {
    joining.value = false
  }
}
</script>

<style scoped>
.join-class-page {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}
.main {
  margin-left: 0;
  flex: 1;
  padding: 0;
}
.tab-bar {
  display: flex;
  background: #fff;
  border-bottom: 1rpx solid #e5e5e5;
}
.tab-item {
  flex: 1;
  text-align: center;
  padding: 30rpx 0;
  font-size: 30rpx;
  color: #666;
  position: relative;
}
.tab-item.active {
  color: #409eff;
  font-weight: bold;
}
.tab-item.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 80rpx;
  height: 6rpx;
  background: #409eff;
  border-radius: 3rpx;
}
.tab-content {
  padding: 40rpx;
}

/* Tab 0: 我的班级 */
.my-classes-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 120rpx 0;
}
.empty-icon {
  font-size: 80rpx;
  margin-bottom: 20rpx;
}
.empty-text {
  font-size: 32rpx;
  color: #666;
  font-weight: bold;
  margin-bottom: 12rpx;
}
.empty-hint {
  font-size: 26rpx;
  color: #999;
}
.loading-state {
  text-align: center;
  padding: 80rpx 0;
  color: #999;
  font-size: 28rpx;
}

/* Tab 1 styles */
.search-section {
  display: flex;
  gap: 20rpx;
  margin-bottom: 40rpx;
}
.phone-input {
  flex: 1;
  height: 88rpx;
  background: #fff;
  border-radius: 12rpx;
  padding: 0 30rpx;
  font-size: 30rpx;
  border: 1rpx solid #e5e5e5;
}
.search-btn {
  height: 88rpx;
  line-height: 88rpx;
  background: #409eff;
  color: #fff;
  border-radius: 12rpx;
  font-size: 30rpx;
  padding: 0 40rpx;
}
.search-btn[disabled] {
  background: #a0cfff;
}

.results-title {
  font-size: 28rpx;
  color: #333;
  margin-bottom: 20rpx;
  font-weight: bold;
}

.class-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 30rpx;
  margin-bottom: 20rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.class-info {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}
.class-name {
  font-size: 30rpx;
  font-weight: bold;
  color: #333;
}
.inst-name {
  font-size: 24rpx;
  color: #999;
}
.subject-text {
  font-size: 24rpx;
  color: #666;
}
.student-count {
  font-size: 24rpx;
  color: #999;
}
.join-btn {
  background: #409eff;
  color: #fff;
  border-radius: 8rpx;
  font-size: 26rpx;
  padding: 16rpx 30rpx;
  white-space: nowrap;
}
.join-btn[disabled] {
  background: #a0cfff;
}

.quit-btn {
  background: #ff4d4f;
  color: #fff;
  border-radius: 8rpx;
  font-size: 26rpx;
  padding: 16rpx 30rpx;
  white-space: nowrap;
}
.quit-btn[disabled] {
  background: #ffaaaa;
}

.empty-result {
  text-align: center;
  padding: 80rpx 0;
  color: #999;
  font-size: 28rpx;
}

/* Tab 2 styles */
.code-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 30rpx;
  padding-top: 60rpx;
}
.code-label {
  font-size: 30rpx;
  color: #333;
  font-weight: bold;
}
.code-input {
  width: 100%;
  max-width: 500rpx;
  height: 100rpx;
  background: #fff;
  border-radius: 12rpx;
  padding: 0 30rpx;
  font-size: 36rpx;
  text-align: center;
  letter-spacing: 8rpx;
  border: 2rpx solid #409eff;
}
.code-submit-btn {
  width: 100%;
  max-width: 500rpx;
  height: 88rpx;
  line-height: 88rpx;
  background: #67c23a;
  color: #fff;
  border-radius: 12rpx;
  font-size: 32rpx;
  margin-top: 20rpx;
}
.code-submit-btn[disabled] {
  background: #b3e67a;
}
</style>
