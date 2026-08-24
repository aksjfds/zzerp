import type { RepositoryFilters } from './types'

export type DepartmentRepositoryQuery = RepositoryFilters & {
  page: number
  page_size: number
}

export type RepositoryWorkshop = {
  id: number
  department_id: number
  workshop_name: string
}
