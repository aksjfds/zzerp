import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { login as loginApi, queryCurrentUser } from '@/api/auth'
import type { LoginPayload, UserProfile } from '@/types/auth'

const USER_STORAGE_KEY = 'zzerp_user'

function readStoredUser() {
  const storedUser = localStorage.getItem(USER_STORAGE_KEY)

  if (!storedUser) {
    return null
  }

  try {
    return JSON.parse(storedUser) as UserProfile
  } catch {
    localStorage.removeItem(USER_STORAGE_KEY)
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserProfile | null>(readStoredUser())
  const loading = ref(false)

  const isLoggedIn = computed(() => Boolean(user.value))
  const permissions = computed(() => user.value?.permissions ?? [])
  const department = computed(() => user.value?.department)

  function setUser(profile: UserProfile) {
    user.value = profile
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(profile))
  }

  async function login(payload: LoginPayload) {
    loading.value = true

    try {
      const profile = await loginApi(payload)
      setUser(profile)
      return profile
    } finally {
      loading.value = false
    }
  }

  async function refreshUser() {
    if (!user.value) {
      return null
    }

    const profile = await queryCurrentUser(user.value.username)
    setUser(profile)
    return profile
  }

  function logout() {
    user.value = null
    localStorage.removeItem(USER_STORAGE_KEY)
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
    hasPermission,
    isLoggedIn,
    loading,
    login,
    logout,
    permissions,
    refreshUser,
    user,
  }
})
