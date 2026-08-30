const BASE = '/api/v1/questions'

function matchFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const token = uni.getStorageSync('accessToken')
  return fetch(BASE + url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options?.headers },
  }).then(async response => {
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.message || `HTTP ${response.status}`)
    return payload
  })
}

export const knowledgeMatchApi = {
  pending: () => matchFetch<any>('/knowledge-matches/pending'),
  preview: (questionIds: string[]) => matchFetch<any>('/knowledge-matches/preview', { method: 'POST', body: JSON.stringify({ question_ids: questionIds }) }),
  rebuild: (questionId: string) => matchFetch<any>(`/${questionId}/knowledge-matches/rebuild`, { method: 'POST', body: '{}' }),
  rebuildBatch: (questionIds?: string[]) => matchFetch<any>('/knowledge-matches/rebuild', { method: 'POST', body: JSON.stringify({ question_ids: questionIds || [] }) }),
  confirm: (items: Array<{ id: string; status: 'confirmed' | 'rejected' }>) => matchFetch<any>('/knowledge-matches/batch-confirm', { method: 'POST', body: JSON.stringify({ matches: items }) }),
}
