import type { LoginAccount, LoginPayload, UserProfile } from '@/types/auth'
import { service } from './request'

export async function login(payload: LoginPayload) {
  const res = await service.post<{ data: UserProfile; csrfToken: string }>('/login', {
    username: payload.username.trim(),
  })

  return res.data.data
}

export async function queryLoginAccounts() {
  const res = await service.get<{ data: LoginAccount[] }>('/login/accounts')
  return res.data.data
}

export async function queryCurrentUser() {
  const res = await service.get<{ data: UserProfile | null; csrfToken?: string }>('/current_user')

  return res.data.data
}

export async function logout() {
  await service.post('/logout')
}
