import { get, post, put, patch, del, type RequestOptions } from '@/utils/request'
import type { UUID } from '@/types/uuid'

export type InstitutionRole = 'admin' | 'teacher'

export interface InstitutionMemberItem {
  id: UUID
  user: UUID
  user_id: UUID
  user_name: string
  user_mobile: string
  role: InstitutionRole
  roles: InstitutionRole[]
  status: string
  user_subject?: string | null
  user_subjects?: string[]
  stages: string[]
}

export interface UpdateInstitutionMemberPayload {
  roles?: InstitutionRole[]
  status?: string
  display_name?: string
  mobile?: string
  subject?: string
  subjects?: string[]
  stages?: string[]
}

export interface AddInstitutionMemberRolesPayload {
  mobile: string
  display_name: string
  roles: InstitutionRole[]
  subject?: string
  subjects?: string[]
  stages?: string[]
}

// === Institution (Admin) ===
export const institutionApi = {
  list: (params?: { name?: string; page?: number; page_size?: number }, options?: RequestOptions) => {
    const qs = params ? '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString() : ''
    return get<{ items: any[]; total: number; page_no: number; page_size: number }>(`/admin/institutions${qs}`, undefined, options)
  },
  create: (data: { institution_name: string; contact_name: string; contact_phone: string; contact_email?: string; address?: string }) =>
    post('/admin/institutions', data),
  detail: (id: UUID) => get(`/admin/institutions/${id}`),
  update: (id: UUID, data: any) => put(`/admin/institutions/${id}`, data),
  updateStatus: (id: UUID, status: string) => put(`/admin/institutions/${id}/status`, { status }),
  remove: (id: UUID) => del(`/admin/institutions/${id}`),
  addMember: (institutionId: UUID, data: { mobile: string; display_name: string; role: InstitutionRole; subject?: string; subjects?: string[]; stages?: string[] }) =>
    post(`/institutions/${institutionId}/members`, data),
  addMemberRoles: async (institutionId: UUID, data: AddInstitutionMemberRolesPayload) => {
    const selectedRoles = (['admin', 'teacher'] as InstitutionRole[]).filter(role => data.roles.includes(role))
    const completedRoles: InstitutionRole[] = []
    for (const role of selectedRoles) {
      let response: any
      try {
        response = await post(`/institutions/${institutionId}/members`, {
          mobile: data.mobile,
          display_name: data.display_name,
          role,
          subject: data.subject,
          subjects: data.subjects,
          stages: data.stages,
        })
      } catch (requestError: any) {
        requestError.completedRoles = completedRoles
        requestError.failedRole = role
        throw requestError
      }
      if (response.code !== 0) {
        const error: any = new Error(response.message || '添加角色失败')
        error.completedRoles = completedRoles
        error.failedRole = role
        throw error
      }
      completedRoles.push(role)
    }
    return { completedRoles }
  },
  members: (institutionId: UUID, params?: { page?: number; page_size?: number; role?: string; status?: string }) => {
    const qs = params ? '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString() : ''
    return get<{ items: InstitutionMemberItem[]; total: number; page: number; page_size: number }>(`/institutions/${institutionId}/members${qs}`)
  },
  updateMember: (institutionId: UUID, userId: UUID, data: UpdateInstitutionMemberPayload) =>
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
  create: (data: { institution_id: UUID; class_name: string; grade_level?: string; description?: string; max_students?: number; allow_invite_join?: boolean }) =>
    post('/classes', data),
  list: (institutionId?: UUID) =>
    get(`/classes${institutionId ? `?institution_id=${institutionId}` : ''}`),
  simpleList: () => get<any[]>('/classes/simple'),
  detail: (id: UUID) => get(`/classes/${id}`),
  update: (id: UUID, data: any) => put(`/classes/${id}`, data),
  remove: (id: UUID) => del(`/classes/${id}`),
  regenerateCode: (id: UUID) => post(`/classes/${id}/regenerate-code`),
  students: (id: UUID) => get(`/classes/${id}/students`),
  importStudents: (id: UUID, file: File) => {
    const token = uni.getStorageSync('accessToken')
    const form = new FormData()
    form.append('file', file)
    return fetch(`/api/v1/classes/${id}/students/import`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form,
    }).then(async response => {
      const data = await response.json()
      if (!response.ok) throw new Error(data.message || '导入失败')
      return data
    })
  },
  learningStats: (id: UUID) => get(`/classes/${id}/learning-stats`),
  removeStudent: (classId: UUID, studentId: UUID) =>
    put(`/classes/${classId}/students/${studentId}`),
  updateStudent: (classId: UUID, studentId: UUID, data: { display_name: string }) =>
    patch(`/classes/${classId}/students/${studentId}`, data),
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
