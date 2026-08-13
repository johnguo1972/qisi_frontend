export type NormalizedInstitutionRole = 'admin' | 'teacher'

const ROLE_ORDER: NormalizedInstitutionRole[] = ['admin', 'teacher']

export function normalizeRoles(roles: unknown, fallbackRole: unknown = 'teacher'): NormalizedInstitutionRole[] {
  const values = Array.isArray(roles) ? roles : []
  const selected = new Set(values.filter((role): role is NormalizedInstitutionRole => ROLE_ORDER.includes(role as NormalizedInstitutionRole)))
  if (selected.size === 0 && ROLE_ORDER.includes(fallbackRole as NormalizedInstitutionRole)) {
    selected.add(fallbackRole as NormalizedInstitutionRole)
  }
  if (selected.size === 0) selected.add('teacher')
  return ROLE_ORDER.filter(role => selected.has(role))
}

export function normalizeMember<T extends Record<string, any>>(member: T): T & { roles: NormalizedInstitutionRole[] } {
  return { ...member, roles: normalizeRoles(member.roles, member.role) }
}
