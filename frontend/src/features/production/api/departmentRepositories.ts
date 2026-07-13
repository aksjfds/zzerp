import { service } from '@/api/request'
import type { RepositoryItem, WorkerItem } from '../domain/types'

export async function queryDepartmentRepositories(departmentCode: string) {
  const response = await service.get<{ data: RepositoryItem[]; total: number }>(
    `/departments/${departmentCode}/repositories`,
    { params: { page: 1, page_size: 10000 } },
  )
  return { items: response.data.data, total: response.data.total }
}

export async function queryDepartmentWorkers(departmentCode: string) {
  const response = await service.get<{ data: WorkerItem[] }>(
    `/departments/${departmentCode}/workers`,
  )
  return response.data.data
}
