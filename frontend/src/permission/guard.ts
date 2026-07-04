import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

function getDefaultDashboardPath(department?: string) {
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
      return getDefaultDashboardPath(authStore.department)
    }

    const permissions = to.meta.permissions as string[] | undefined
    if (permissions?.length && !authStore.hasPermission(permissions)) {
      return to.path === '/forbidden' ? true : '/forbidden'
    }

    return true
  })
}
