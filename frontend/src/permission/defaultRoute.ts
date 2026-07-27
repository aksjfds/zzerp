import type { UserProfile } from '@/types/auth'
import { getDepartmentModule } from '@/features/departments/registry'

export function getDefaultDashboardPath(user?: UserProfile | null) {
  if (!user) return '/login'
  if (user.username === 'admin' || user.role === 'admin') return '/admin'
  if (user.department === 'pmc') return '/pmc'
  if (user.department === 'business') return '/business/orders'
  const departmentModule = getDepartmentModule(user.department)
  if (departmentModule) return departmentModule.routePath
  return user.department ? '/products' : '/login'
}
