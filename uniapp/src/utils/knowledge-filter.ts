export interface KnowledgePoint {
  id: number
  label: string
  full_label: string
  module: string
  parent_id: number | null
  level: number
}

/**
 * Filter knowledge points by matching `module` or `full_label` (case-insensitive).
 */
export function filterKnowledgePoints(points: KnowledgePoint[], searchTerm: string): KnowledgePoint[] {
  if (!searchTerm.trim()) return []
  const term = searchTerm.toLowerCase()
  return points.filter((kp) =>
    (kp.module || '').toLowerCase().includes(term) ||
    (kp.label || '').toLowerCase().includes(term)
  )
}
