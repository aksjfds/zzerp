import { computed, ref } from 'vue'
import { isAxiosError } from 'axios'
import { defineStore } from 'pinia'
import { clearCsrfToken } from '@/api/request'
import { login as loginApi, logout as logoutApi, queryCurrentUser } from './api'
import type { LoginPayload, UserProfile } from './types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserProfile | null>(null)
  const loading = ref(false)
  const initialized = ref(false)

  const isLoggedIn = computed(() => Boolean(user.value))
  const permissions = computed(() => user.value?.permissions ?? [])

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
      user.value = profile
      initialized.value = true
      return profile
    } catch (error) {
      if (isAxiosError(error) && error.response?.status === 401) {
        user.value = null
        initialized.value = true
        return null
      }
      throw error
    }
  }

  async function logout() {
    await logoutApi()
    clearSession()
  }

  function clearSession() {
    clearCsrfToken()
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
