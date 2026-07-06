<template>
  <view class="institution-page">
    <view class="header">
      <text class="page-title">机构管理</text>
      <button class="create-btn" @click="goCreate">+ 创建机构</button>
    </view>

    <view v-if="loading" class="loading">
      <text>加载中...</text>
    </view>

    <view v-else-if="institutions.length === 0" class="empty">
      <text>暂无机构，点击右上角"创建机构"开始</text>
    </view>

    <view v-else class="list">
      <view v-for="inst in institutions" :key="inst.id" class="card">
        <view class="card-main" @click="goDetail(inst.id)">
          <view class="card-header">
            <text class="card-name">{{ inst.institution_name }}</text>
            <view class="status-tag" :class="statusClass(inst.status)">
              <text class="status-text">{{ statusText(inst.status) }}</text>
            </view>
          </view>
          <view class="card-info">
            <text class="info-item">教师：{{ inst.teacher_count || 0 }} 人</text>
            <text class="info-item">班级：{{ inst.class_count || 0 }} 个</text>
          </view>
          <view v-if="inst.contact_name || inst.contact_phone" class="card-contact">
            <text v-if="inst.contact_name">联系人：{{ inst.contact_name }}</text>
            <text v-if="inst.contact_phone"> | {{ inst.contact_phone }}</text>
          </view>
        </view>
        <view class="card-actions">
          <button class="action-btn btn-edit" @click.stop="goEdit(inst.id)">编辑</button>
          <button class="action-btn btn-delete" @click.stop="confirmDelete(inst)">删除</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { institutionApi } from '@/api/institutions.ts'

const institutions = ref<any[]>([])
const loading = ref(false)

async function loadInstitutions() {
  loading.value = true
  try {
    const res = await institutionApi.list({ page: 1, page_size: 50 })
    institutions.value = res.data?.items || []
  } catch (e) {
    console.error('Failed to load institutions:', e)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onMounted(loadInstitutions)
let hasLoaded = false
onShow(() => {
  if (hasLoaded) loadInstitutions()
  hasLoaded = true
})

function statusText(status: string): string {
  const map: Record<string, string> = { active: '正常', suspended: '已暂停', closed: '已关闭' }
  return map[status] || status
}

function statusClass(status: string): string {
  const map: Record<string, string> = { active: 'tag-active', suspended: 'tag-suspended', closed: 'tag-closed' }
  return map[status] || ''
}

function goCreate() { uni.navigateTo({ url: '/pages/admin/institution-create' }) }
function goDetail(id: number) { uni.navigateTo({ url: `/pages/admin/institution-detail?id=${id}` }) }
function goEdit(id: number) { uni.navigateTo({ url: `/pages/admin/institution-edit?id=${id}` }) }

async function confirmDelete(inst: any) {
  uni.showModal({
    title: '确认删除',
    content: `确定要删除机构"${inst.institution_name}"吗？\n\n删除前必须先删除所有班级和老师。`,
    success: async (res) => {
      if (res.confirm) {
        try {
          await institutionApi.remove(inst.id)
          uni.showToast({ title: '删除成功', icon: 'success' })
          await loadInstitutions()
        } catch (e: any) {
          const msg = e?.data?.message || '删除失败'
          uni.showToast({ title: msg, icon: 'none', duration: 3000 })
        }
      }
    }
  })
}
</script>

<style scoped>
.institution-page {
  min-height: 100vh;
  background: #f0f2f5;
  padding: 30rpx 40rpx;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.create-btn {
  background: #409eff;
  color: #fff;
  font-size: 26rpx;
  border-radius: 8rpx;
  border: none;
  padding: 12rpx 24rpx;
}
.loading {
  text-align: center;
  padding: 80rpx;
  color: #999;
  font-size: 26rpx;
}
.empty {
  text-align: center;
  padding: 120rpx 40rpx;
  color: #999;
  font-size: 26rpx;
  background: #fff;
  border-radius: 12rpx;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
.card {
  background: #fff;
  border-radius: 12rpx;
  padding: 28rpx 32rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.card-main {
  cursor: pointer;
}
.card-main:hover {
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.card-name {
  font-size: 30rpx;
  font-weight: bold;
  color: #333;
}
.status-tag {
  padding: 4rpx 16rpx;
  border-radius: 20rpx;
  font-size: 22rpx;
}
.tag-active {
  background: #e8f5e9;
  color: #4caf50;
}
.tag-suspended {
  background: #fff3e0;
  color: #ff9800;
}
.tag-closed {
  background: #fce4ec;
  color: #e74c3c;
}
.status-text {
  font-size: 22rpx;
}
.card-info {
  display: flex;
  gap: 40rpx;
  margin-bottom: 12rpx;
}
.info-item {
  font-size: 24rpx;
  color: #666;
}
.card-contact {
  font-size: 22rpx;
  color: #999;
}
.card-actions {
  display: flex;
  gap: 16rpx;
  margin-top: 20rpx;
  padding-top: 20rpx;
  border-top: 1rpx solid #f0f0f0;
}
.action-btn {
  flex: 1;
  font-size: 24rpx;
  border-radius: 6rpx;
  border: none;
  padding: 10rpx;
}
.btn-edit {
  background: #ecf5ff;
  color: #409eff;
}
.btn-delete {
  background: #fff0f0;
  color: #e74c3c;
}
</style>
