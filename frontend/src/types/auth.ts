import type { Department } from '@/types/production'

export type UserDepartment = Department | 'sys'

export type UserProfile = {
  id: number
  username: string
  name: string
  department: UserDepartment
  role: string
  permissions: string[]
}

export type LoginPayload = {
  username: string
  password: string
}
