<template>
  <view class="detail-page">
    <!-- 机构信息卡片 -->
    <view class="info-card">
      <view class="card-header">
        <text class="card-title">{{ institution.institution_name }}</text>
        <view class="status-tag" :class="statusClass(institution.status)">
          <text class="status-text">{{ statusText(institution.status) }}</text>
        </view>
      </view>
      <view class="info-grid">
        <view class="info-row">
          <text class="info-label">联系人</text>
          <text class="info-value">{{ institution.contact_name || '-' }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">联系电话</text>
          <text class="info-value">{{ institution.contact_phone || '-' }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">联系邮箱</text>
          <text class="info-value">{{ institution.contact_email || '-' }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">机构地址</text>
          <text class="info-value">{{ institution.address || '-' }}</text>
        </view>
      </view>
    </view>

    <!-- 成员管理 -->
    <view class="member-section">
      <view class="section-header">
        <text class="section-title">成员管理</text>
      </view>

      <!-- 添加成员表单 -->
      <view class="add-member-form">
        <view class="form-row">
          <view class="form-item">
            <text class="label">手机号 *</text>
            <input v-model="memberForm.mobile" type="number" placeholder="请输入手机号" />
          </view>
          <view class="form-item">
            <text class="label">姓名 *</text>
            <input v-model="memberForm.display_name" placeholder="请输入姓名" />
          </view>
        </view>
        <view class="form-row">
          <view class="form-item">
            <text class="label">角色 *</text>
            <picker mode="selector" :range="roleLabelsAdd" :value="addRoleIndex" @change="memberForm.role = roleOptions[$event.detail.value].value">
              <view class="picker-display">{{ selectedRoleLabel }}</view>
            </picker>
          </view>
          <view class="form-item">
            <text class="label">科目</text>
            <picker mode="selector" :range="subjectLabelsAdd" :value="addSubjectIndex" @change="memberForm.subject = subjectOptions[$event.detail.value].value">
              <view class="picker-display">{{ selectedSubjectLabel }}</view>
            </picker>
          </view>
        </view>
        <view class="form-row">
          <view class="form-item full-width">
            <text class="label">学段（可多选）</text>
            <view class="checkbox-group">
              <view v-for="opt in stageOptions" :key="opt.value" class="checkbox-item" @click="toggleStage(opt.value)">
                <text class="checkbox-icon" :class="{ checked: memberForm.stages.includes(opt.value) }">{{ memberForm.stages.includes(opt.value) ? '✓' : '○' }}</text>
                <text class="checkbox-label">{{ opt.label }}</text>
              </view>
            </view>
          </view>
        </view>
        <button class="add-btn" @click="handleAddMember">添加成员</button>
      </view>

      <!-- 成员列表 -->
      <view v-if="members.length === 0" class="member-empty">
        <text>暂无成员</text>
      </view>
      <view v-else class="member-list">
        <view v-for="m in members" :key="m.id" class="member-card">
          <view class="member-main" @click="openEditModal(m)">
            <text class="member-name">{{ m.user_name || m.display_name || '-' }}</text>
            <text class="member-phone">{{ m.user_mobile || m.mobile || '-' }}</text>
            <text v-if="m.user_subject" class="member-subject">{{ subjectText(m.user_subject) }}</text>
            <view v-if="m.role === 'teacher' && m.stages && m.stages.length > 0" class="member-stages">
              <text v-for="s in m.stages" :key="s" class="stage-tag">{{ s }}</text>
            </view>
          </view>
          <view class="member-actions">
            <view class="role-badge" :class="roleClass(m.role)" @click.stop="handleToggleRole(m)">
              <text class="role-text">{{ roleText(m.role) }}</text>
            </view>
            <view class="status-badge" :class="m.status === 'active' ? 'status-active' : 'status-removed'" @click.stop="handleToggleStatus(m)">
              <text class="status-text-small">{{ m.status === 'active' ? '在职' : '已移除' }}</text>
            </view>
            <view class="remove-btn" @click.stop="handleRemoveMember(m)" v-if="m.status === 'active'">
              <text class="remove-text">移除</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 编辑成员弹窗 -->
    <view v-if="showEditModal" class="modal-overlay" @click="closeEditModal">
      <view class="modal-content" @click.stop>
        <view class="modal-header">
          <text class="modal-title">编辑成员信息</text>
          <text class="modal-close" @click="closeEditModal">&times;</text>
        </view>
        <view class="modal-body">
          <view class="edit-form">
            <view class="edit-item">
              <text class="edit-label">姓名</text>
              <input v-model="editForm.display_name" placeholder="请输入姓名" />
            </view>
            <view class="edit-item">
              <text class="edit-label">手机号</text>
              <input v-model="editForm.mobile" type="number" placeholder="请输入手机号" />
            </view>
            <view class="edit-item">
              <text class="edit-label">角色</text>
              <picker mode="selector" :range="roleLabels" :value="editRoleIndex" @change="editForm.role = roleOptions[$event.detail.value].value">
                <view class="picker-display">{{ editRoleLabel }}</view>
              </picker>
            </view>
            <view class="edit-item">
              <text class="edit-label">科目</text>
              <picker mode="selector" :range="subjectLabels" :value="editSubjectIndex" @change="editForm.subject = subjectOptions[$event.detail.value].value">
                <view class="picker-display">{{ editSubjectLabel }}</view>
              </picker>
            </view>
            <view class="edit-item">
              <text class="edit-label">学段（可多选）</text>
              <view class="checkbox-group">
                <view v-for="opt in stageOptions" :key="opt.value" class="checkbox-item" @click="toggleEditStage(opt.value)">
                  <text class="checkbox-icon" :class="{ checked: editForm.stages.includes(opt.value) }">{{ editForm.stages.includes(opt.value) ? '✓' : '○' }}</text>
                  <text class="checkbox-label">{{ opt.label }}</text>
                </view>
              </view>
            </view>
          </view>
        </view>
        <view class="modal-footer">
          <button class="modal-btn cancel" @click="closeEditModal">取消</button>
          <button class="modal-btn confirm" @click="handleSaveEdit">保存</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { institutionApi } from '@/api/institutions.ts'

const institutionId = ref<number>(0)
const institution = ref<any>({})
const members = ref<any[]>([])
const loading = ref(false)

const roleOptions = [
  { label: '系统管理员', value: 'admin' },
  { label: '教师', value: 'teacher' },
]

const subjectOptions = [
  { label: '未设置', value: '' },
  { label: '语文', value: '语文' },
  { label: '数学', value: '数学' },
  { label: '英语', value: '英语' },
  { label: '物理', value: '物理' },
  { label: '化学', value: '化学' },
  { label: '生物', value: '生物' },
  { label: '地理', value: '地理' },
  { label: '历史', value: '历史' },
]

const stageOptions = [
  { label: '小学', value: '小学' },
  { label: '初中', value: '初中' },
  { label: '高中', value: '高中' },
]

const memberForm = ref({ mobile: '', display_name: '', role: 'teacher', subject: '', stages: [] as string[] })

// Edit modal state
const showEditModal = ref(false)
const editForm = ref({ user_id: 0, display_name: '', mobile: '', role: 'teacher', subject: '', stages: [] as string[] })

const selectedRoleLabel = computed(() => {
  const opt = roleOptions.find(o => o.value === memberForm.value.role)
  return opt?.label || '教师'
})

const selectedSubjectLabel = computed(() => {
  const opt = subjectOptions.find(o => o.value === memberForm.value.subject)
  return opt?.label || '未设置'
})

const addRoleIndex = computed(() => {
  const idx = roleOptions.findIndex(o => o.value === memberForm.value.role)
  return idx >= 0 ? idx : 0
})

const addSubjectIndex = computed(() => {
  const idx = subjectOptions.findIndex(o => o.value === memberForm.value.subject)
  return idx >= 0 ? idx : 0
})

// Simple string arrays for picker range
const roleLabelsAdd = computed(() => roleOptions.map(o => o.label))
const subjectLabelsAdd = computed(() => subjectOptions.map(o => o.label))

const editRoleIndex = computed(() => {
  const idx = roleOptions.findIndex(o => o.value === editForm.value.role)
  return idx >= 0 ? idx : 0
})

const editRoleLabel = computed(() => {
  const opt = roleOptions.find(o => o.value === editForm.value.role)
  return opt?.label || '教师'
})

const editSubjectIndex = computed(() => {
  const idx = subjectOptions.findIndex(o => o.value === editForm.value.subject)
  return idx >= 0 ? idx : 0
})

const editSubjectLabel = computed(() => {
  const opt = subjectOptions.find(o => o.value === editForm.value.subject)
  return opt?.label || '未设置'
})

// Simple string arrays for picker range (more reliable than object arrays)
const roleLabels = computed(() => roleOptions.map(o => o.label))
const subjectLabels = computed(() => subjectOptions.map(o => o.label))

onLoad((options: any) => {
  const id = parseInt(options?.id || '0')
  institutionId.value = id
})

onMounted(() => {
  if (!institutionId.value) {
    uni.showToast({ title: '缺少机构ID', icon: 'none' })
    return
  }
  loadData()
})
let hasLoaded = false
onShow(() => {
  if (hasLoaded) {
    loadData()
  }
  hasLoaded = true
})

async function loadData() {
  loading.value = true
  try {
    const [instRes, membersRes] = await Promise.all([
      institutionApi.detail(institutionId.value),
      institutionApi.members(institutionId.value, { page_size: 1000 }),
    ])
    institution.value = instRes.data || {}
    const membersData = membersRes.data
    members.value = Array.isArray(membersData) ? membersData : (membersData?.items || [])
  } catch (e) {
    console.error('Failed to load institution data:', e)
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function subjectText(subject: string): string {
  const opt = subjectOptions.find(o => o.value === subject)
  return opt?.label || ''
}

function toggleStage(value: string) {
  const idx = memberForm.value.stages.indexOf(value)
  if (idx >= 0) {
    memberForm.value.stages.splice(idx, 1)
  } else {
    memberForm.value.stages.push(value)
  }
}

function toggleEditStage(value: string) {
  const idx = editForm.value.stages.indexOf(value)
  if (idx >= 0) {
    editForm.value.stages.splice(idx, 1)
  } else {
    editForm.value.stages.push(value)
  }
}

function statusText(status: string): string {
  const map: Record<string, string> = { active: '正常', suspended: '已暂停', closed: '已关闭' }
  return map[status] || status
}

function statusClass(status: string): string {
  const map: Record<string, string> = { active: 'tag-active', suspended: 'tag-suspended', closed: 'tag-closed' }
  return map[status] || ''
}

function roleText(role: string): string {
  const map: Record<string, string> = { teacher: '教师', admin: '系统管理员' }
  return map[role] || role
}

function roleClass(role: string): string {
  return role === 'admin' ? 'badge-admin' : 'badge-teacher'
}

async function handleAddMember() {
  if (!memberForm.value.mobile.trim()) {
    uni.showToast({ title: '请输入手机号', icon: 'none' })
    return
  }
  if (!memberForm.value.display_name.trim()) {
    uni.showToast({ title: '请输入姓名', icon: 'none' })
    return
  }

  try {
    const res: any = await institutionApi.addMember(institutionId.value, {
      mobile: memberForm.value.mobile.trim(),
      display_name: memberForm.value.display_name.trim(),
      role: memberForm.value.role,
      subject: memberForm.value.subject,
      stages: memberForm.value.stages,
    })
    if (res.code === 0) {
      uni.showToast({ title: '添加成功', icon: 'success' })
      memberForm.value = { mobile: '', display_name: '', role: 'teacher', subject: '', stages: [] }
      await loadData()
    } else {
      uni.showToast({ title: res.message || '添加失败', icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: '添加失败', icon: 'none' })
  }
}

// --- Edit Modal ---

function openEditModal(member: any) {
  const stages = member.stages || []
  editForm.value = {
    user_id: member.user_id || member.user,
    display_name: member.user_name || '',
    mobile: member.user_mobile || '',
    role: member.role || 'teacher',
    subject: member.user_subject || '',
    stages: Array.isArray(stages) ? stages : [],
  }
  showEditModal.value = true
}

function closeEditModal() {
  showEditModal.value = false
}

async function handleSaveEdit() {
  if (!editForm.value.display_name.trim()) {
    uni.showToast({ title: '姓名不能为空', icon: 'none' })
    return
  }
  if (!editForm.value.mobile.trim()) {
    uni.showToast({ title: '手机号不能为空', icon: 'none' })
    return
  }

  try {
    const res: any = await institutionApi.updateMember(institutionId.value, editForm.value.user_id, {
      display_name: editForm.value.display_name.trim(),
      mobile: editForm.value.mobile.trim(),
      role: editForm.value.role,
      subject: editForm.value.subject,
      stages: editForm.value.stages,
    })
    if (res.code === 0) {
      uni.showToast({ title: '保存成功', icon: 'success' })
      closeEditModal()
      await loadData()
    } else {
      uni.showToast({ title: res.message || '保存失败', icon: 'none' })
    }
  } catch (e: any) {
    uni.showToast({ title: '保存失败', icon: 'none' })
  }
}

async function handleToggleRole(member: any) {
  const newRole = member.role === 'teacher' ? 'admin' : 'teacher'
  const roleLabel = newRole === 'admin' ? '系统管理员' : '教师'

  uni.showModal({
    title: '确认修改角色',
    content: `将 ${member.user_name} 的角色改为${roleLabel}？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          const resp: any = await institutionApi.updateMember(institutionId.value, member.user_id, { role: newRole })
          if (resp.code === 0) {
            uni.showToast({ title: '修改成功', icon: 'success' })
            await loadData()
          } else {
            uni.showToast({ title: resp.message || '修改失败', icon: 'none' })
          }
        } catch (e) {
          uni.showToast({ title: '修改失败', icon: 'none' })
        }
      }
    }
  })
}

async function handleToggleStatus(member: any) {
  const newStatus = member.status === 'active' ? 'removed' : 'active'
  const statusLabel = newStatus === 'active' ? '恢复在职' : '移除成员'

  uni.showModal({
    title: '确认修改状态',
    content: `确定要${statusLabel} ${member.user_name} 吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          const resp: any = await institutionApi.updateMember(institutionId.value, member.user_id, { status: newStatus })
          if (resp.code === 0) {
            uni.showToast({ title: '修改成功', icon: 'success' })
            await loadData()
          } else {
            uni.showToast({ title: resp.message || '修改失败', icon: 'none' })
          }
        } catch (e) {
          uni.showToast({ title: '修改失败', icon: 'none' })
        }
      }
    }
  })
}

function handleRemoveMember(member: any) {
  uni.showModal({
    title: '确认移除成员',
    content: `确定要移除 ${member.user_name} 吗？`,
    success: async (res) => {
      if (res.confirm) {
        try {
          const resp: any = await institutionApi.removeMember(institutionId.value, member.user_id)
          if (resp.code === 0) {
            uni.showToast({ title: '已移除', icon: 'success' })
            await loadData()
          } else {
            uni.showToast({ title: resp.message || '移除失败', icon: 'none' })
          }
        } catch (e) {
          uni.showToast({ title: '移除失败', icon: 'none' })
        }
      }
    }
  })
}
</script>

<style scoped>
.detail-page { min-height: 100vh; background: #f0f2f5; padding: 30rpx 40rpx; }
.info-card { background: #fff; border-radius: 12rpx; padding: 32rpx; margin-bottom: 30rpx; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24rpx; padding-bottom: 20rpx; border-bottom: 1rpx solid #f0f0f0; }
.card-title { font-size: 32rpx; font-weight: bold; color: #333; }
.status-tag { padding: 4rpx 16rpx; border-radius: 20rpx; }
.tag-active { background: #e8f5e9; color: #4caf50; }
.tag-suspended { background: #fff3e0; color: #ff9800; }
.tag-closed { background: #fce4ec; color: #e74c3c; }
.status-text { font-size: 22rpx; }
.info-grid { display: flex; flex-direction: column; gap: 16rpx; }
.info-row { display: flex; justify-content: space-between; padding: 8rpx 0; }
.info-label { font-size: 24rpx; color: #999; }
.info-value { font-size: 24rpx; color: #333; }

.member-section { background: #fff; border-radius: 12rpx; padding: 32rpx; }
.section-header { margin-bottom: 24rpx; }
.section-title { font-size: 28rpx; font-weight: bold; color: #333; }
.add-member-form { background: #fafafa; border-radius: 8rpx; padding: 24rpx; margin-bottom: 24rpx; }
.form-row { display: flex; gap: 16rpx; margin-bottom: 16rpx; }
.form-item { flex: 1; }
.label { font-size: 22rpx; color: #666; margin-bottom: 8rpx; display: block; }
input { display: block; width: 100%; height: 48px; line-height: 24px; border: 1rpx solid #ddd; border-radius: 6px; padding: 12px; font-size: 24rpx; background: #fff; box-sizing: border-box; }
.picker-display { padding: 12rpx; background: #fff; border: 1rpx solid #ddd; border-radius: 6rpx; font-size: 24rpx; color: #333; }
.full-width { flex: 1 1 100%; }
.checkbox-group { display: flex; gap: 24rpx; margin-top: 8rpx; }
.checkbox-item { display: flex; align-items: center; gap: 8rpx; cursor: pointer; padding: 8rpx 16rpx; border-radius: 8rpx; background: #fafafa; }
.checkbox-item:active { background: #f0f0f0; }
.checkbox-icon { font-size: 28rpx; color: #999; width: 32rpx; text-align: center; }
.checkbox-icon.checked { color: #409eff; font-weight: bold; }
.checkbox-label { font-size: 24rpx; color: #333; }
.add-btn { background: #409eff; color: #fff; font-size: 26rpx; border-radius: 6rpx; border: none; padding: 12rpx; }
.member-empty { text-align: center; padding: 60rpx; color: #999; font-size: 26rpx; }
.member-list { display: flex; flex-direction: column; gap: 12rpx; }

.member-card { display: flex; justify-content: space-between; align-items: center; padding: 20rpx 24rpx; background: #fafafa; border-radius: 8rpx; }
.member-main { flex: 1; cursor: pointer; display: flex; flex-direction: column; gap: 4rpx; }
.member-main:active { opacity: 0.7; }
.member-name { font-size: 26rpx; font-weight: bold; color: #333; }
.member-phone { font-size: 22rpx; color: #999; }
.member-subject { font-size: 20rpx; color: #409eff; }
.member-stages { display: flex; gap: 8rpx; margin-top: 4rpx; flex-wrap: wrap; }
.stage-tag { font-size: 18rpx; color: #1976d2; background: #e3f2fd; padding: 2rpx 12rpx; border-radius: 8rpx; }
.member-actions { display: flex; align-items: center; gap: 12rpx; }
.role-badge { padding: 4rpx 16rpx; border-radius: 20rpx; font-size: 22rpx; }
.badge-teacher { background: #e3f2fd; color: #1976d2; }
.badge-admin { background: #f3e5f5; color: #7b1fa2; }
.role-text { font-size: 22rpx; }
.status-badge { padding: 4rpx 12rpx; border-radius: 12rpx; font-size: 20rpx; }
.status-active { background: #e8f5e9; color: #4caf50; }
.status-removed { background: #f5f5f5; color: #999; }
.status-text-small { font-size: 20rpx; }
.remove-btn { padding: 4rpx 16rpx; border-radius: 12rpx; background: #ffebee; }
.remove-text { font-size: 22rpx; color: #e74c3c; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 999; display: flex; align-items: center; justify-content: center; }
.modal-content { background: #fff; border-radius: 16rpx; width: 85%; max-width: 600rpx; overflow: hidden; }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 24rpx 32rpx; border-bottom: 1rpx solid #f0f0f0; }
.modal-title { font-size: 32rpx; font-weight: bold; color: #333; }
.modal-close { font-size: 48rpx; color: #999; line-height: 1; }
.modal-body { padding: 32rpx; }
.edit-form { display: flex; flex-direction: column; gap: 24rpx; }
.edit-item { display: flex; flex-direction: column; gap: 8rpx; }
.edit-label { font-size: 24rpx; color: #666; }
.modal-footer { display: flex; gap: 16rpx; padding: 24rpx 32rpx; border-top: 1rpx solid #f0f0f0; }
.modal-btn { flex: 1; border-radius: 8rpx; border: none; padding: 16rpx; font-size: 28rpx; }
.modal-btn.cancel { background: #f5f5f5; color: #666; }
.modal-btn.confirm { background: #409eff; color: #fff; }
</style>
