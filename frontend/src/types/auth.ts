import type { Department } from '@/types/production'

export type UserDepartment =
  | Department
  | 'sys'
  | 'engineering'
  | 'business'
  | 'planning'

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
}

export type LoginAccount = {
  username: string
  department: UserDepartment
  departmentName: string
  role: string
}
