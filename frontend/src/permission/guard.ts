import type { Router } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

function getDefaultDashboardPath(department?: string) {
  if (!department || department === 'sys') {
    return '/dashboard'
  }

  return `/dashboard/${department}`
}

export function setupRouterGuard(router: Router) {
  router.beforeEach((to) => {
    const authStore = useAuthStore()

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

    const routeDepartment = to.meta.department as string | undefined
    if (
      routeDepartment
      && authStore.department !== 'sys'
      && authStore.department !== routeDepartment
    ) {
      return getDefaultDashboardPath(authStore.department)
    }

    const permissions = to.meta.permissions as string[] | undefined
    if (permissions?.length && !authStore.hasPermission(permissions)) {
      return getDefaultDashboardPath(authStore.department)
    }

    return true
  })
}
