import type { UserProfile } from '@/types/auth'
import { getDepartmentModule } from '@/features/departments'
import { ORDER_PERMISSIONS, PRODUCT_PERMISSIONS } from './constants'

export function getDefaultDashboardPath(user?: UserProfile | null) {
  if (!user) return '/login'
  if (user.is_system) {
    if (user.permissions.includes(PRODUCT_PERMISSIONS.view)) return '/products'
    if (user.permissions.includes(ORDER_PERMISSIONS.view)) return '/business/orders'
    return '/forbidden'
  }
  if (user.department === 'business') return '/business/orders'
  if (!user.department) return '/login'
  const departmentModule = getDepartmentModule(user.department)
  if (departmentModule) return departmentModule.routePath
  return '/products'
}
