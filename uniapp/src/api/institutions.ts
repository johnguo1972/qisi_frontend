import { get, post, put, del } from '@/utils/request'
import type { UUID } from '@/types/uuid'

// === Institution (Admin) ===
export const institutionApi = {
  list: (params?: { name?: string; page?: number; page_size?: number }) => {
    const qs = params ? '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString() : ''
    return get<{ items: any[]; total: number; page_no: number; page_size: number }>(`/admin/institutions${qs}`)
  },
  create: (data: { institution_name: string; contact_name: string; contact_phone: string; contact_email?: string; address?: string }) =>
    post('/admin/institutions', data),
  detail: (id: UUID) => get(`/admin/institutions/${id}`),
  update: (id: UUID, data: any) => put(`/admin/institutions/${id}`, data),
  updateStatus: (id: UUID, status: string) => put(`/admin/institutions/${id}/status`, { status }),
  remove: (id: UUID) => del(`/admin/institutions/${id}`),
  addMember: (institutionId: UUID, data: { mobile: string; display_name: string; role: string }) =>
    post(`/institutions/${institutionId}/members`, data),
  members: (institutionId: UUID, params?: { page?: number; page_size?: number; role?: string; status?: string }) => {
    const qs = params ? '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString() : ''
    return get(`/institutions/${institutionId}/members${qs}`)
  },
  updateMember: (institutionId: UUID, userId: UUID, data: { role?: string; status?: string; display_name?: string; mobile?: string }) =>
    put(`/institutions/${institutionId}/members/${userId}`, data),
  removeMember: (institutionId: UUID, userId: UUID) =>
    put(`/institutions/${institutionId}/members/${userId}`, { status: 'removed' }),
}

// === Teacher: My Institutions ===
export const teacherApi = {
  institutions: () => get<{ id: UUID; institution_name: string }[]>('/teacher/institutions'),
}

// === Class (Teacher) ===
export const classApi = {
  create: (data: { institution_id: UUID; class_name: string; description?: string; max_students?: number; allow_invite_join?: boolean }) =>
    post('/classes', data),
  list: (institutionId?: UUID) =>
    get(`/classes${institutionId ? `?institution_id=${institutionId}` : ''}`),
  simpleList: () => get<any[]>('/classes/simple'),
  detail: (id: UUID) => get(`/classes/${id}`),
  update: (id: UUID, data: any) => put(`/classes/${id}`, data),
  remove: (id: UUID) => del(`/classes/${id}`),
  regenerateCode: (id: UUID) => post(`/classes/${id}/regenerate-code`),
  students: (id: UUID) => get(`/classes/${id}/students`),
  learningStats: (id: UUID) => get(`/classes/${id}/learning-stats`),
  removeStudent: (classId: UUID, studentId: UUID) =>
    put(`/classes/${classId}/students/${studentId}`),
  joinRequests: (classId: UUID) => get(`/classes/${classId}/join-requests`),
  approveRequest: (requestId: UUID) => post(`/classes/join-requests/${requestId}/approve`),
  rejectRequest: (requestId: UUID) => post(`/classes/join-requests/${requestId}/reject`),
  quitClass: (classId: UUID) => post(`/classes/${classId}/quit`),
}

// === Student ===
export const studentClassApi = {
  search: (teacherMobile: string) =>
    post('/student/classes/search', { teacher_mobile: teacherMobile }),
  joinByCode: (data: { invite_code: string; applicant_name: string; applicant_phone?: string }) =>
    post('/student/classes/join-by-code', data),
  myClasses: () => get('/student/my-classes'),
  submitJoinRequest: (data: { class_id: UUID; request_type: string; applicant_phone: string; message?: string }) =>
    post('/classes/join-request', data),
  myJoinRequests: () => get('/student/join-requests'),
}
