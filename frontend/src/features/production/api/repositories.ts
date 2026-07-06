import { service } from '@/api/request'
import type { RepositoryItem } from '../domain/types'

export async function queryDepartmentRepositories(departmentCode: string) {
  const response = await service.get<{ data: RepositoryItem[] }>(
    `/departments/${departmentCode}/repositories`,
  )
  return response.data.data
}
