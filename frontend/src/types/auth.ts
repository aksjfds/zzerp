export type UserDepartment = 'engineering' | 'sys'

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
