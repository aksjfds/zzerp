import { service } from '@/api/request'
import type {
  AdminWorkerDepartment,
  AdminWorkerHistoryItem,
} from '../domain/types'

export async function queryAdminWorkerOverview() {
  const response = await service.get<{ data: AdminWorkerDepartment[] }>('/admin/workers/overview')
  return response.data.data
}

export async function queryAdminWorkerHistory(workerId: number, month: string) {
  const response = await service.get<{ data: AdminWorkerHistoryItem[] }>(
    `/admin/workers/${workerId}/work-history`,
    { params: { month } },
  )
  return response.data.data
}
