import { get } from '@/utils/request.ts'

export interface KnowledgePoint {
  id: number
  name: string
  question_count: number
}

export interface Chapter {
  name: string
  knowledge_points: KnowledgePoint[]
}

export interface Semester {
  name: string
  chapters: Chapter[]
}

export interface Grade {
  name: string
  semesters: Semester[]
}

export interface KnowledgeTree {
  grades: Grade[]
}

export const knowledgeApi = {
  // GET /api/v1/teacher/knowledge-tree
  getTree: (params?: { subject?: string; stages?: string }) => {
    const query: Record<string, string> = {}
    if (params?.subject) query.subject = params.subject
    if (params?.stages) query.stages = params.stages
    return get<KnowledgeTree>('/teacher/knowledge-tree/', query)
  },
  // Alias for convenience: knowledgeApi.tree('math')
  tree: (subject: string) => knowledgeApi.getTree({ subject }),
}
