import type { UserProfile } from './types'
import { PLAN_PERMISSIONS, PRODUCT_PERMISSIONS } from './permissions'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { useAuthStore } from './store'

export function getDefaultDashboardPath(user?: UserProfile | null) {
  if (!user) return '/login'
  if (user.department_code) return `/departments/${encodeURIComponent(user.department_code)}/work-orders`
  if (user.permissions.includes(PLAN_PERMISSIONS.view)) return '/production-plans'
  if (user.permissions.includes(PRODUCT_PERMISSIONS.view)) return '/products'
  return '/forbidden'
}

export function useSessionNavigation() {
  const auth = useAuthStore()
  const router = useRouter()
  const signingOut = ref(false)

  async function logout() {
    if (signingOut.value) return
    signingOut.value = true
    try {
      await auth.logout()
      await router.replace('/login')
    } catch (cause) {
      ElMessage.error(getApiErrorDetail(cause)?.message || '退出登录失败，请重试')
    } finally {
      signingOut.value = false
    }
  }
  return { logout, signingOut }
}
