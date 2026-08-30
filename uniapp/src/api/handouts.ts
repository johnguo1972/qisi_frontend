import type { UUID } from '@/types/uuid'

const BASE = '/api/v1'

function handoutFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const token = uni.getStorageSync('accessToken')
  return fetch(BASE + url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  }).then(async response => {
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.message || `HTTP ${response.status}`)
    return payload
  })
}

export const handoutApi = {
  list: () => handoutFetch<any>('/handouts/'),
  create: (data: { name: string; subject: string; stage?: string; grade?: string; course?: UUID }) =>
    handoutFetch<any>('/handouts/', { method: 'POST', body: JSON.stringify(data) }),
  detail: (id: UUID) => handoutFetch<any>(`/handouts/${id}/`),
  replaceQuestions: (id: UUID, questionIds: string[], sourceTypes?: Record<string, string>) =>
    handoutFetch<any>(`/handouts/${id}/questions/replace/`, {
      method: 'POST', body: JSON.stringify({ question_ids: questionIds, source_types: sourceTypes || {} }),
    }),
  preview: (id: UUID) => handoutFetch<any>(`/handouts/${id}/preview/`),
  publish: (id: UUID) => handoutFetch<any>(`/handouts/${id}/publish/`, { method: 'POST', body: '{}' }),
  exportPdf: (id: UUID) => handoutFetch<any>(`/handouts/${id}/export-pdf/`, { method: 'POST', body: '{}' }),
  courseClasses: (courseId: UUID) => handoutFetch<any>(`/courses/${courseId}/classes/`),
  courseHandouts: (courseId: UUID) => handoutFetch<any>(`/courses/${courseId}/handouts/`),
  attachClass: (courseId: UUID, classId: UUID) =>
    handoutFetch<any>(`/courses/${courseId}/classes/`, { method: 'POST', body: JSON.stringify({ class_id: classId }) }),
  attachHandout: (courseId: UUID, handoutId: UUID, sortNo = 1) =>
    handoutFetch<any>(`/courses/${courseId}/handouts/`, { method: 'POST', body: JSON.stringify({ handout_id: handoutId, sort_no: sortNo }) }),
  removeClass: (courseId: UUID, classId: UUID) =>
    handoutFetch<any>(`/courses/${courseId}/classes/${classId}/`, { method: 'DELETE', body: '{}' }),
  removeHandout: (courseId: UUID, handoutId: UUID) =>
    handoutFetch<any>(`/courses/${courseId}/handouts/${handoutId}/`, { method: 'DELETE', body: '{}' }),
}
