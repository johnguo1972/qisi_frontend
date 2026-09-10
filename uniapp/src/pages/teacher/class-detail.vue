<template>
  <view class="class-detail">
    <view class="main">
      <view class="page-header">
        <button class="btn-back" @click="goBack">返回</button>
        <text class="page-title">{{ classInfo.class_name || '班级详情' }}</text>
        <view class="page-actions"><button class="btn-edit" @click="goEdit">编辑</button><button class="btn-delete" @click="confirmDelete">删除</button></view>
      </view>
      <view v-if="loading" class="loading">加载中...</view>
      <template v-else-if="classInfo.id">
        <view class="info-card">
          <view class="info-row"><text class="info-label">班级名称</text><text class="info-value">{{ classInfo.class_name }}</text></view>
          <view class="info-row"><text class="info-label">班级编号</text><text class="info-value">{{ classInfo.class_no }}</text></view>
          <view class="info-row"><text class="info-label">班级年级</text><text class="info-value">{{ classInfo.grade_level || '未设置' }}</text></view>
          <view class="info-row"><text class="info-label">班级描述</text><text class="info-value">{{ classInfo.description || '暂无描述' }}</text></view>
          <view class="info-row"><text class="info-label">最大学生数</text><text class="info-value">{{ classInfo.max_students || '不限制' }}</text></view>
          <view class="info-row invite-row"><view class="invite-section"><text class="info-label">邀请码</text><text class="invite-code">{{ classInfo.invite_code }}</text></view><button class="btn-refresh" size="mini" @click="handleRefreshCode">刷新邀请码</button><button class="btn-copy" size="mini" @click="copyInviteCode">复制邀请码</button></view>
        </view>
        <view class="action-bar"><button class="btn-add-student" @click="openAddStudent">添加学生</button><button class="btn-import" @click="goImport">批量导入学生</button><button class="btn-requests" @click="goRequests">申请审批<text v-if="pendingCount > 0" class="badge">{{ pendingCount }}</text></button></view>
        <view class="student-section">
          <view class="section-header"><text class="section-title">学生列表 ({{ students.length }})</text></view>
          <view v-if="students.length === 0" class="empty">暂无学生加入</view>
          <view v-else class="student-table">
            <view class="student-table-header"><text class="col-name">姓名</text><text class="col-school">学校</text><text class="col-grade">年级</text><text class="col-class">班级</text><text class="col-type">班型</text><text class="col-phone">手机号</text><text class="col-parent">家长手机号</text><text class="col-join">加入方式</text><text class="col-action">操作</text></view>
            <view v-for="s in students" :key="s.id" class="student-row"><text class="col-name">{{ s.student_name }}</text><text class="col-school">{{ s.school || '未设置' }}</text><text class="col-grade">{{ s.grade_level || '未设置' }}</text><text class="col-class">{{ s.class_name || classInfo.class_name }}</text><text class="col-type">{{ classTypeText(s.class_type) }}</text><text class="col-phone">{{ maskPhone(s.student_mobile) || '未设置' }}</text><text class="col-parent">{{ maskPhone(s.parent_mobile) || '未设置' }}</text><text class="col-join" :class="'badge-' + s.join_type">{{ joinTypeText(s.join_type) }}</text><view class="col-action"><button size="mini" class="student-action-btn edit-student" @click.stop="openEditStudent(s)">编辑</button><button size="mini" class="student-action-btn remove-student" @click="removeStudent(s)">移除</button></view></view>
          </view>
        </view>
        <view v-if="studentDialogOpen" class="modal-mask" @click.self="closeStudentDialog"><view class="edit-dialog student-dialog"><text class="edit-dialog-title">{{ editingStudent ? '编辑学生' : '添加学生' }}</text><view class="student-form-grid"><view class="form-field"><text class="form-label">学生姓名<text class="required">*</text></text><input v-model="studentForm.student_name" class="form-input" maxlength="64" placeholder="请输入学生姓名" /></view><view class="form-field"><text class="form-label">学校<text class="required">*</text></text><input v-model="studentForm.school" class="form-input" maxlength="100" placeholder="请输入学校" /></view><view class="form-field"><text class="form-label">年级<text class="required">*</text></text><picker :range="gradeOptions" :value="gradeIndex" @change="selectGrade"><view class="picker-display">{{ studentForm.grade_level || '请选择年级' }}</view></picker></view><view class="form-field"><text class="form-label">班级<text class="required">*</text></text><picker :range="classOptions" range-key="class_name" :value="classIndex" @change="selectClass"><view class="picker-display">{{ selectedClassName || '请选择班级' }}</view></picker></view><view class="form-field"><text class="form-label">班型</text><picker :range="classTypeOptions" :value="classTypeIndex" @change="selectClassType"><view class="picker-display">{{ classTypeText(studentForm.class_type) || '请选择班型' }}</view></picker></view><view class="form-field"><text class="form-label">学生手机号<text class="required">*</text></text><input v-model="studentForm.student_mobile" class="form-input" type="number" maxlength="11" placeholder="请输入学生手机号" /></view><view class="form-field"><text class="form-label">家长姓名</text><input v-model="studentForm.parent_name" class="form-input" maxlength="64" placeholder="请输入家长姓名" /></view><view class="form-field"><text class="form-label">家长手机号</text><input v-model="studentForm.parent_mobile" class="form-input" type="number" maxlength="11" placeholder="请输入家长手机号" /></view></view><view class="edit-dialog-actions"><button class="edit-cancel" @click="closeStudentDialog">取消</button><button class="edit-confirm" :disabled="savingStudent" @click="saveStudent">{{ savingStudent ? '保存中...' : '保存' }}</button></view></view></view>
      </template>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { classApi, type AddStudentPayload, type ClassSimpleItem, type UpdateStudentPayload } from '@/api/institutions'
import type { UUID } from '@/types/uuid'

interface ClassInfo { id: UUID; class_name: string; class_no: string; grade_level?: string | null; description?: string; invite_code?: string; max_students?: number; pending_request_count?: number; status?: string }
interface Student { id: UUID; student: UUID; student_name: string; student_mobile?: string; school?: string | null; grade_level?: string | null; class_id?: UUID; class_name?: string; class_type?: 'S' | 'A_PLUS' | 'A' | '' | null; parent_id?: UUID | null; parent_name?: string | null; parent_mobile?: string | null; join_type?: string; status?: string }
interface StudentForm { student_name: string; school: string; grade_level: string; target_class_id: UUID | ''; class_type: 'S' | 'A_PLUS' | 'A' | ''; student_mobile: string; parent_name: string; parent_mobile: string }

const classInfo = reactive<ClassInfo>({} as ClassInfo)
const students = ref<Student[]>([])
const classOptions = ref<ClassSimpleItem[]>([])
const loading = ref(false)
const studentDialogOpen = ref(false)
const editingStudent = ref<Student | null>(null)
const savingStudent = ref(false)
const openAddAfterLoad = ref(false)
const classTypeOptions = ['S班', 'A+班', 'A班']
const classTypeCodes: Array<'S' | 'A_PLUS' | 'A'> = ['S', 'A_PLUS', 'A']
const studentForm = reactive<StudentForm>({ student_name: '', school: '', grade_level: '', target_class_id: '', class_type: '', student_mobile: '', parent_name: '', parent_mobile: '' })
let classId: UUID = ''

const gradeOptions = computed(() => Array.from(new Set(classOptions.value.map(item => item.grade_level).filter(Boolean))) as string[])
const gradeIndex = computed(() => Math.max(0, gradeOptions.value.indexOf(studentForm.grade_level)))
const classIndex = computed(() => Math.max(0, classOptions.value.findIndex(item => String(item.id) === String(studentForm.target_class_id))))
const selectedClassName = computed(() => classOptions.value.find(item => String(item.id) === String(studentForm.target_class_id))?.class_name || '')
const classTypeIndex = computed(() => Math.max(0, classTypeCodes.indexOf(studentForm.class_type as any)))
const pendingCount = computed(() => classInfo.pending_request_count || 0)

onLoad(async (options: any) => { classId = String(options?.classId || '') as UUID; openAddAfterLoad.value = String(options?.openAdd || '') === '1'; if (!classId) { uni.showToast({ title: '缺少班级ID', icon: 'none' }); return } await loadClassDetail(); await loadClassOptions(); if (openAddAfterLoad.value) openAddStudent() })
onShow(async () => { if (classId && !studentDialogOpen.value) await loadClassDetail() })
async function loadClassDetail() { loading.value = true; try { const response: any = await classApi.detail(classId); if (response?.data) Object.assign(classInfo, response.data); await loadStudents() } catch (error) { console.error('Failed to load class detail', error); uni.showToast({ title: '加载班级信息失败', icon: 'none' }) } finally { loading.value = false } }
async function loadStudents() { const response: any = await classApi.students(classId); students.value = response?.data?.items || [] }
async function loadClassOptions() { try { const response: any = await classApi.simpleList(); classOptions.value = response?.data || [] } catch (error) { console.error('Failed to load teacher classes', error) } }
function resetStudentForm() { Object.assign(studentForm, { student_name: '', school: '', grade_level: String(classInfo.grade_level || ''), target_class_id: classId, class_type: '', student_mobile: '', parent_name: '', parent_mobile: '' }) }
function openAddStudent() { editingStudent.value = null; resetStudentForm(); studentDialogOpen.value = true }
function openEditStudent(student: Student) { editingStudent.value = student; Object.assign(studentForm, { student_name: student.student_name || '', school: student.school || '', grade_level: student.grade_level || String(classInfo.grade_level || ''), target_class_id: student.class_id || classId, class_type: student.class_type || '', student_mobile: student.student_mobile || '', parent_name: student.parent_name || '', parent_mobile: student.parent_mobile || '' }); studentDialogOpen.value = true }
function closeStudentDialog() { studentDialogOpen.value = false; editingStudent.value = null }
function selectGrade(event: any) { studentForm.grade_level = gradeOptions.value[Number(event?.detail?.value ?? 0)] || '' }
function selectClass(event: any) { const target = classOptions.value[Number(event?.detail?.value ?? 0)]; studentForm.target_class_id = target?.id || ''; if (target?.grade_level) studentForm.grade_level = target.grade_level }
function selectClassType(event: any) { studentForm.class_type = classTypeCodes[Number(event?.detail?.value ?? 0)] || '' }
function validateStudentForm() { const form = studentForm; if (!form.student_name.trim() || !form.school.trim() || !form.grade_level || !form.target_class_id || !/^1[3-9]\d{9}$/.test(form.student_mobile.trim())) { uni.showToast({ title: '请完整填写学生姓名、学校、年级、班级和正确的学生手机号', icon: 'none' }); return false }; if (Boolean(form.parent_name.trim()) !== Boolean(form.parent_mobile.trim())) { uni.showToast({ title: '家长姓名和家长手机号必须同时填写或同时为空', icon: 'none' }); return false }; if (form.parent_mobile && !/^1[3-9]\d{9}$/.test(form.parent_mobile.trim())) { uni.showToast({ title: '家长手机号格式不正确', icon: 'none' }); return false }; if (form.parent_mobile && form.parent_mobile.trim() === form.student_mobile.trim()) { uni.showToast({ title: '学生和家长不能使用同一个手机号', icon: 'none' }); return false }; return true }
async function saveStudent() { if (!validateStudentForm() || savingStudent.value) return; savingStudent.value = true; const payload: AddStudentPayload & UpdateStudentPayload = { ...studentForm, student_name: studentForm.student_name.trim(), school: studentForm.school.trim(), grade_level: studentForm.grade_level.trim(), student_mobile: studentForm.student_mobile.trim(), parent_name: studentForm.parent_name.trim(), parent_mobile: studentForm.parent_mobile.trim() }; try { const response: any = editingStudent.value ? await classApi.updateStudent(classId, editingStudent.value.student, payload) : await classApi.addStudent(classId, payload); if (response?.code !== 0) { uni.showToast({ title: response?.message || '保存失败', icon: 'none' }); return }; const targetClassId = String(studentForm.target_class_id); const wasEditing = Boolean(editingStudent.value); closeStudentDialog(); uni.showToast({ title: wasEditing ? '学生信息更新成功' : '学生添加成功', icon: 'success' }); if (targetClassId !== String(classId)) { uni.redirectTo({ url: `/pages/teacher/class-detail?classId=${targetClassId}&view=students` }); return }; await loadStudents() } catch (error: any) { uni.showToast({ title: error?.message || '保存失败，请重试', icon: 'none' }) } finally { savingStudent.value = false } }
function maskPhone(phone?: string | null) { if (!phone) return ''; return phone.length === 11 ? `${phone.substring(0, 3)}****${phone.substring(7)}` : phone }
function classTypeText(value?: string | null) { return value === 'S' ? 'S班' : value === 'A_PLUS' ? 'A+班' : value === 'A' ? 'A班' : '未设置' }
function joinTypeText(value?: string) { return ({ direct: '直接加入', invite: '邀请码加入', by_code: '邀请码加入', manual: '手动加入', import: '导入加入', approved: '审核通过', pending: '待审核' } as Record<string, string>)[value || ''] || value || '未知' }
function goBack() { uni.navigateBack() }
function goEdit() { uni.navigateTo({ url: `/pages/teacher/class-edit?id=${classId}` }) }
function goRequests() { uni.navigateTo({ url: `/pages/teacher/class-requests?classId=${classId}` }) }
function goImport() { uni.navigateTo({ url: `/pages/teacher/student-import?classId=${classId}` }) }
function copyInviteCode() { if (!classInfo.invite_code) return; uni.setClipboardData({ data: classInfo.invite_code, success: () => uni.showToast({ title: '邀请码已复制', icon: 'success' }) }) }
async function handleRefreshCode() { try { await classApi.regenerateCode(classId); const response: any = await classApi.detail(classId); if (response?.data) Object.assign(classInfo, response.data); uni.showToast({ title: '邀请码已刷新', icon: 'success' }) } catch { uni.showToast({ title: '刷新失败', icon: 'none' }) } }
async function removeStudent(student: Student) { const result = await new Promise<UniApp.ShowModalRes>(resolve => uni.showModal({ title: '移除学生', content: `确定移除${student.student_name}？`, success: resolve })); if (!result.confirm) return; try { await classApi.removeStudent(classId, student.student); await loadStudents(); uni.showToast({ title: '已移除', icon: 'success' }) } catch { uni.showToast({ title: '移除失败', icon: 'none' }) } }
function confirmDelete() { uni.showModal({ title: '确认删除', content: `确定删除班级“${classInfo.class_name}”吗？`, success: async result => { if (!result.confirm) return; try { await classApi.remove(classId); uni.showToast({ title: '删除成功', icon: 'success' }); setTimeout(() => uni.navigateBack(), 800) } catch (error: any) { uni.showToast({ title: error?.message || '删除失败', icon: 'none' }) } } }) }
</script>

<style scoped>
.class-detail { min-height: 100vh; background: #f0f2f5; }.main { padding: 30rpx 40rpx; }.page-header { display: grid; grid-template-columns: minmax(120rpx, 1fr) auto minmax(120rpx, 1fr); align-items: center; min-height: 72rpx; padding-bottom: 28rpx; }.page-title { color: #333; font-size: 36rpx; font-weight: bold; text-align: center; }.page-actions { display: flex; justify-self: end; gap: 12rpx; } button { margin: 0; }.btn-back, .btn-edit, .btn-delete, .btn-add-student, .btn-import, .btn-requests, .btn-refresh, .btn-copy { border: 0; border-radius: 8rpx; font-size: 24rpx; }.btn-back { justify-self: start; padding: 8rpx 20rpx; color: #666; background: #fff; border: 1rpx solid #dcdfe6; }.btn-edit { padding: 8rpx 20rpx; color: #409eff; background: #ecf5ff; }.btn-delete { padding: 8rpx 20rpx; color: #e74c3c; background: #fff0f0; }.info-card, .student-section { padding: 32rpx; margin-bottom: 20rpx; background: #fff; border-radius: 12rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.05); }.info-row { display: flex; justify-content: space-between; padding: 16rpx 0; border-bottom: 1rpx solid #f0f0f0; }.info-row:last-child { border-bottom: 0; }.info-label { min-width: 160rpx; color: #999; font-size: 26rpx; }.info-value { color: #333; font-size: 26rpx; }.invite-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 16rpx; }.invite-section { display: flex; gap: 20rpx; align-items: center; }.invite-code { color: #409eff; font-size: 28rpx; font-weight: bold; letter-spacing: 4rpx; }.btn-refresh, .btn-copy { padding: 6rpx 16rpx; }.btn-refresh { color: #409eff; background: #ecf5ff; }.btn-copy { color: #67c23a; background: #f0f9eb; }.action-bar { display: flex; gap: 16rpx; margin-bottom: 20rpx; }.btn-add-student { padding: 16rpx 32rpx; color: #fff; background: #67c23a; }.btn-import { padding: 16rpx 32rpx; color: #409eff; background: #ecf5ff; }.btn-requests { display: inline-flex; align-items: center; gap: 8rpx; padding: 16rpx 32rpx; color: #fff; background: #409eff; }.badge { min-width: 32rpx; padding: 2rpx 10rpx; color: #fff; background: #e74c3c; border-radius: 50%; font-size: 20rpx; text-align: center; }.section-title { color: #333; font-size: 28rpx; font-weight: bold; }.section-header { margin-bottom: 20rpx; }.empty, .loading { padding: 60rpx; color: #999; font-size: 26rpx; text-align: center; }.student-table { min-width: 1250px; overflow-x: auto; }.student-table-header, .student-row { display: flex; align-items: center; }.student-table-header { padding: 12rpx 0; border-bottom: 2rpx solid #e0e0e0; font-weight: bold; }.student-row { padding: 16rpx 0; border-bottom: 1rpx solid #f0f0f0; }.col-name, .col-school, .col-grade, .col-class, .col-type, .col-phone, .col-parent, .col-join { flex: 0 0 130px; color: #606266; font-size: 24rpx; }.col-name { flex-basis: 150px; color: #333; }.col-action { display: flex; flex: 0 0 150px; justify-content: center; gap: 8px; }.student-action-btn { width: 68px; height: 40px; padding: 0; border-radius: 6px; font-size: 22rpx; line-height: 40px; }.edit-student { color: #409eff; background: #ecf5ff; }.remove-student { color: #f56c6c; background: #fff5f5; }.modal-mask { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,.45); }.edit-dialog { width: 760rpx; max-width: calc(100vw - 64rpx); padding: 32rpx; background: #fff; border-radius: 12rpx; box-sizing: border-box; }.edit-dialog-title { display: block; margin-bottom: 24rpx; color: #303133; font-size: 30rpx; font-weight: 600; }.student-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20rpx; max-height: 65vh; overflow-y: auto; }.form-field { min-width: 0; }.form-label { display: block; margin-bottom: 8rpx; color: #606266; font-size: 24rpx; }.required { color: #f56c6c; }.form-input, .picker-display { width: 100%; height: 72rpx; padding: 0 20rpx; border: 1rpx solid #dcdfe6; border-radius: 8rpx; box-sizing: border-box; color: #303133; background: #fff; font-size: 26rpx; line-height: 72rpx; }.picker-display { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.edit-dialog-actions { display: flex; justify-content: flex-end; gap: 16rpx; margin-top: 28rpx; }.edit-dialog-actions button { padding: 8rpx 28rpx; border-radius: 8rpx; font-size: 24rpx; }.edit-cancel { color: #606266; background: #f5f7fa; }.edit-confirm { color: #fff; background: #409eff; }
@media (max-width: 768px) { .main { padding: 20rpx; }.page-header { grid-template-columns: auto 1fr auto; column-gap: 12rpx; }.page-title { font-size: 30rpx; }.action-bar { flex-wrap: wrap; }.invite-row { display: flex; flex-wrap: wrap; }.invite-section { width: 100%; }.student-section { padding: 20rpx; overflow-x: auto; }.student-form-grid { grid-template-columns: 1fr; } }
</style>

<style scoped>
/* Use the full content width while retaining horizontal scrolling on narrow screens. */
.student-table {
  width: 100%;
  min-width: 0;
  overflow-x: auto;
}
.student-table-header,
.student-row {
  display: grid;
  grid-template-columns: 1.15fr 1.15fr .9fr 1.15fr .9fr 1.25fr 1.25fr 1.1fr 150px;
  width: 100%;
  min-width: 1120px;
  box-sizing: border-box;
  column-gap: 16px;
}
.student-table-header > text,
.student-row > text,
.student-row > .col-action {
  min-width: 0;
  width: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.col-name, .col-school, .col-grade, .col-class, .col-type,
.col-phone, .col-parent, .col-join, .col-action {
  flex: none;
}
.col-action {
  display: flex;
  justify-content: center;
  gap: 8px;
}
</style>
