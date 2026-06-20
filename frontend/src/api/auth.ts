import type { LoginPayload, UserProfile } from '@/types/auth'
import { service } from './request'

export async function login(payload: LoginPayload) {
  const res = await service.post<{ data: UserProfile }>('/login', {
    username: payload.username.trim(),
    password: payload.password,
  })

  return res.data.data
}

export async function queryCurrentUser(username: string) {
  const res = await service.get<{ data: UserProfile }>('/current_user', {
    params: {
      username,
    },
  })

  return res.data.data
}
