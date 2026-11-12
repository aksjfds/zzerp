import type { UserProfile } from '@/types/auth'
import { PLAN_PERMISSIONS, PRODUCT_PERMISSIONS } from './constants'

export function getDefaultDashboardPath(user?: UserProfile | null) {
  if (!user) return '/login'
  if (user.department_code) return `/departments/${encodeURIComponent(user.department_code)}/work-orders`
  if (user.permissions.includes(PLAN_PERMISSIONS.view)) return '/production-plans'
  if (user.permissions.includes(PRODUCT_PERMISSIONS.view)) return '/products'
  return '/forbidden'
}
