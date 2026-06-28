import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi, queryCurrentUser } from '@/api/auth'
import type { LoginPayload, UserProfile } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserProfile | null>(null)
  const loading = ref(false)
  const initialized = ref(false)

  const isLoggedIn = computed(() => Boolean(user.value))
  const permissions = computed(() => user.value?.permissions ?? [])
  const department = computed(() => user.value?.department)

  function setUser(profile: UserProfile) {
    user.value = profile
  }

  async function login(payload: LoginPayload) {
    loading.value = true

    try {
      const profile = await loginApi(payload)
      setUser(profile)
      initialized.value = true
      return profile
    } finally {
      loading.value = false
    }
  }

  async function refreshUser() {
    try {
      const profile = await queryCurrentUser()
      setUser(profile)
      return profile
    } catch {
      user.value = null
      return null
    } finally {
      initialized.value = true
    }
  }

  async function logout() {
    try {
      await logoutApi()
    } finally {
      user.value = null
      initialized.value = true
    }
  }

  function clearSession() {
    user.value = null
    initialized.value = true
  }

  function hasPermission(permission?: string | string[]) {
    if (!permission) {
      return true
    }

    const requiredPermissions = Array.isArray(permission) ? permission : [permission]
    return requiredPermissions.some((item) => permissions.value.includes(item))
  }

  return {
    department,
    clearSession,
    hasPermission,
    initialized,
    isLoggedIn,
    loading,
    login,
    logout,
    permissions,
    refreshUser,
    user,
  }
})
