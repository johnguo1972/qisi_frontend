import { get, post, put, del } from '@/utils/request.ts'

// === Institution (Admin) ===
export const institutionApi = {
  list: (params?: { name?: string; page?: number; page_size?: number }) => {
    const qs = params ? '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString() : ''
    return get<{ items: any[]; total: number; page_no: number; page_size: number }>(`/admin/institutions${qs}`)
  },
  create: (data: { institution_name: string; contact_name: string; contact_phone: string; contact_email?: string; address?: string }) =>
    post('/admin/institutions', data),
  detail: (id: number) => get(`/admin/institutions/${id}`),
  update: (id: number, data: any) => put(`/admin/institutions/${id}`, data),
  updateStatus: (id: number, status: string) => put(`/admin/institutions/${id}/status`, { status }),
  remove: (id: number) => del(`/admin/institutions/${id}`),
  addMember: (institutionId: number, data: { mobile: string; display_name: string; role: string }) =>
    post(`/institutions/${institutionId}/members`, data),
  members: (institutionId: number, params?: { page?: number; page_size?: number; role?: string; status?: string }) => {
    const qs = params ? '?' + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString() : ''
    return get(`/institutions/${institutionId}/members${qs}`)
  },
  updateMember: (institutionId: number, userId: number, data: { role?: string; status?: string; display_name?: string; mobile?: string }) =>
    put(`/institutions/${institutionId}/members/${userId}`, data),
  removeMember: (institutionId: number, userId: number) =>
    put(`/institutions/${institutionId}/members/${userId}`, { status: 'removed' }),
}

// === Teacher: My Institutions ===
export const teacherApi = {
  institutions: () => get<{ id: number; institution_name: string }[]>('/teacher/institutions'),
}

// === Class (Teacher) ===
export const classApi = {
  create: (data: { institution_id: number; class_name: string; description?: string; max_students?: number; allow_invite_join?: boolean }) =>
    post('/classes', data),
  list: (institutionId?: number) =>
    get(`/classes${institutionId ? `?institution_id=${institutionId}` : ''}`),
  simpleList: () => get<any[]>('/classes/simple'),
  detail: (id: number) => get(`/classes/${id}`),
  update: (id: number, data: any) => put(`/classes/${id}`, data),
  remove: (id: number) => del(`/classes/${id}`),
  regenerateCode: (id: number) => post(`/classes/${id}/regenerate-code`),
  students: (id: number) => get(`/classes/${id}/students`),
  removeStudent: (classId: number, studentId: number) =>
    put(`/classes/${classId}/students/${studentId}`),
  joinRequests: (classId: number) => get(`/classes/${classId}/join-requests`),
  approveRequest: (requestId: number) => post(`/classes/join-requests/${requestId}/approve`),
  rejectRequest: (requestId: number) => post(`/classes/join-requests/${requestId}/reject`),
  quitClass: (classId: number) => post(`/classes/${classId}/quit`),
}

// === Student ===
export const studentClassApi = {
  search: (teacherMobile: string) =>
    post('/student/classes/search', { teacher_mobile: teacherMobile }),
  joinByCode: (data: { invite_code: string; applicant_name: string; applicant_phone?: string }) =>
    post('/student/classes/join-by-code', data),
  myClasses: () => get('/student/my-classes'),
  submitJoinRequest: (data: { class_id: number; request_type: string; applicant_phone: string; message?: string }) =>
    post('/classes/join-request', data),
  myJoinRequests: () => get('/student/join-requests'),
}
