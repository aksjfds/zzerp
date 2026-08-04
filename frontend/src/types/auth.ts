export type UserDepartment = 'assembly' | 'business' | 'cnc' | 'engineering' | 'finished' | 'pmc' | 'polish' | 'qc' | 'stamp' | 'sys' | 'warehouse'

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
