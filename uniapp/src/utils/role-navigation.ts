import type { AppRole } from '@/utils/roles'

/**
 * H5/App 的角色工作台入口。
 * MP-Weixin 继续使用各端现有抽屉/页面路由，不调用本工具。
 */
export function roleLayoutPath(role: AppRole): string {
  if (role === 'admin') return '/pages/admin/home'
  if (role === 'teacher') return '/pages/teacher/layout'
  if (role === 'parent') return '/pages/parent/layout'
  return '/pages/student/layout'
}

export function roleSectionPath(role: AppRole, section?: string): string {
  const base = roleLayoutPath(role)
  return section ? `${base}?section=${encodeURIComponent(section)}` : base
}

/**
 * 从带侧栏的深层页面切回角色工作台。
 * reLaunch 用于清除详情页/中间页栈，确保菜单切换后不会再出现错误返回路径。
 */
export function navigateRoleSection(role: AppRole, section: string): void {
  uni.reLaunch({ url: roleSectionPath(role, section) })
}
