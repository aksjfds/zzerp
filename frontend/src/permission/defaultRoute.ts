import type { UserProfile } from '@/types/auth'

const PRODUCTION_DEPARTMENTS = new Set(['stamp', 'cnc', 'polish', 'qc', 'assembly', 'warehouse'])

export function getDefaultDashboardPath(user?: UserProfile | null) {
  if (!user) return '/login'
  if (user.username === 'admin' || user.role === 'admin') return '/admin'
  if (user.department === 'pmc') return '/pmc'
  if (user.department === 'business') return '/business/orders'
  if (PRODUCTION_DEPARTMENTS.has(user.department ?? '')) return `/${user.department}`
  return user.department ? '/products' : '/login'
}
