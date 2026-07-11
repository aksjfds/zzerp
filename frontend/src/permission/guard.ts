import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile } from '@/types/auth'

function getDefaultDashboardPath(user?: UserProfile | null) {
  if (!user) return '/login'
  if (user.username === 'admin' || user.role === 'admin') return '/admin'
  const department = user.department
  if (department === 'business') return '/business/orders'
  if (['stamp', 'polish', 'qc', 'assembly'].includes(department ?? '')) {
    return `/${department}`
  }
  return department ? '/products' : '/login'
}

export function setupRouterGuard(router: Router) {
  router.beforeEach(async (to) => {
    const authStore = useAuthStore()

    if (!authStore.initialized) {
      await authStore.refreshUser()
    }

    if (to.meta.requiresAuth && !authStore.isLoggedIn) {
      return {
        path: '/login',
        query: {
          redirect: to.fullPath,
        },
      }
    }

    if (to.path === '/login' && authStore.isLoggedIn) {
      return getDefaultDashboardPath(authStore.user)
    }

    const permissions = to.meta.permissions as string[] | undefined
    if (permissions?.length && !authStore.hasPermission(permissions)) {
      return to.path === '/forbidden' ? true : '/forbidden'
    }

    return true
  })
}
