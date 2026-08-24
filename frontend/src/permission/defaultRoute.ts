import type { UserProfile } from '@/types/auth'
import { getDepartmentModule } from '@/features/departments'

export function getDefaultDashboardPath(user?: UserProfile | null) {
  if (!user) return '/login'
  if (user.is_system) return '/admin'
  if (user.department === 'pmc') return '/pmc'
  if (user.department === 'business') return '/business/orders'
  if (!user.department) return '/login'
  const departmentModule = getDepartmentModule(user.department)
  if (departmentModule) return departmentModule.routePath
  return '/products'
}
