export type UserProfile = {
  id: number
  username: string
  name: string
  is_system: boolean
  role: string
  department_code?: string | null
  permissions: string[]
}

export type LoginPayload = {
  username: string
  password: string
}
