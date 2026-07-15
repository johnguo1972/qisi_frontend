<template>
  <view class="my-classes">

    <!-- 右侧内容区 -->
    <view class="main">
      <view class="page-header">
        <text class="page-title">我的班级</text>
        <button class="btn-create" @click="goCreate">+ 创建班级</button>
      </view>
      <view v-if="loading" class="loading">
        <text>加载中...</text>
      </view>
      <view v-else-if="classes.length === 0" class="empty">
        <text>还没有班级，点击"创建班级"开始</text>
      </view>
      <view v-else class="class-grid">
        <view v-for="cls in classes" :key="cls.id" class="class-card">
          <view class="card-main" @click="goDetail(cls.id)">
            <view class="card-header">
              <text class="class-name">{{ cls.class_name }}</text>
              <text class="class-no">编号: {{ cls.class_no }}</text>
            </view>
            <view class="card-body">
              <text class="class-desc">{{ cls.description || '暂无描述' }}</text>
            </view>
            <view class="card-footer">
              <text class="student-count">👥 {{ cls.student_count || 0 }} 名学生</text>
              <text v-if="cls.pending_requests && cls.pending_requests > 0" class="pending-badge">
                {{ cls.pending_requests }} 个待审批
              </text>
            </view>
          </view>
          <view class="card-actions">
            <button class="action-btn btn-edit" @click.stop="goEdit(cls.id)">编辑</button>
            <button class="action-btn btn-delete" @click.stop="confirmDelete(cls)">删除</button>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { classApi } from '@/api/index.ts'

interface ClassItem {
  id: number
  class_name: string
  class_no: string
  description?: string
  student_count?: number
  pending_requests?: number
  invite_code?: string
  max_students?: number
  status?: string
}

const classes = ref<ClassItem[]>([])
const loading = ref(false)

onMounted(async () => {
  await loadClasses()
})

async function loadClasses() {
  loading.value = true
  try {
    const res = await classApi.list()
    classes.value = res.data?.items || []
  } catch (e) {
    console.error('Failed to load classes:', e)
    uni.showToast({ title: '加载班级列表失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function goCreate() { uni.navigateTo({ url: '/pages/teacher/class-create' }) }
function goDetail(id: number) { uni.navigateTo({ url: `/pages/teacher/class-detail?classId=${id}` }) }
function goEdit(id: number) { uni.navigateTo({ url: `/pages/teacher/class-edit?id=${id}` }) }

async function confirmDelete(cls: ClassItem) {
  uni.showModal({
    title: '确认删除',
    content: `确定要删除班级"${cls.class_name}"吗？\n\n删除前必须先移除所有学生和老师。`,
    success: async (res) => {
      if (res.confirm) {
        try {
          const resp: any = await classApi.remove(cls.id)
          if (resp && resp.code === 0) {
            uni.showToast({ title: '删除成功', icon: 'success' })
            await loadClasses()
          } else {
            uni.showToast({ title: resp?.message || '删除失败', icon: 'none', duration: 4000 })
          }
        } catch (e: any) {
          const msg = e?.data?.message || e?.message || '删除失败'
          uni.showToast({ title: msg, icon: 'none', duration: 4000 })
        }
      }
    }
  })
}
</script>

<style scoped>
.my-classes {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}
.main {
  margin-left: 0;
  flex: 1;
  padding: 30rpx 40rpx;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10rpx 0 30rpx;
}
.page-title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}
.btn-create {
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  padding: 12rpx 28rpx;
  font-size: 26rpx;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-create:hover {
  background: #337ecc;
}
.class-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20rpx;
}
.class-card {
  background: #fff;
  border-radius: 12rpx;
  padding: 24rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.05);
}
.card-main {
  cursor: pointer;
}
.card-main:hover {
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.1);
}
.card-actions {
  display: flex;
  gap: 12rpx;
  margin-top: 16rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid #f0f0f0;
}
.action-btn {
  flex: 1;
  font-size: 22rpx;
  border-radius: 6rpx;
  border: none;
  padding: 8rpx;
}
.btn-edit {
  background: #ecf5ff;
  color: #409eff;
}
.btn-delete {
  background: #fff0f0;
  color: #e74c3c;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}
.class-name {
  font-size: 28rpx;
  font-weight: bold;
  color: #333;
}
.class-no {
  font-size: 20rpx;
  color: #999;
}
.card-body {
  margin-bottom: 12rpx;
}
.class-desc {
  font-size: 22rpx;
  color: #666;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12rpx;
  border-top: 1rpx solid #f0f0f0;
}
.student-count {
  font-size: 22rpx;
  color: #999;
}
.pending-badge {
  font-size: 20rpx;
  color: #e6a23c;
  background: #fdf6ec;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}
.loading, .empty {
  text-align: center;
  padding: 80rpx;
  color: #999;
  font-size: 26rpx;
}

/* 小屏适配 */
@media (max-width: 768px) {
  .main {
    margin-left: 60px;
    padding: 20rpx;
  }
  .class-grid {
    grid-template-columns: 1fr;
  }
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16rpx;
  }
}
</style>