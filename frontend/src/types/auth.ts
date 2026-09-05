export type UserDepartment = 'assembly' | 'business' | 'cnc' | 'engineering' | 'finished' | 'outsource' | 'polish' | 'qc' | 'stamp' | 'warehouse'

export type UserProfile = {
  id: number
  username: string
  name: string
  department: UserDepartment | null
  is_system: boolean
  role: string
  permissions: string[]
}

export type LoginPayload = {
  username: string
  password: string
}
