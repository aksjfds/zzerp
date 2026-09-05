import { service } from '@/api/request'
import type {
  DepartmentWorkerOverview,
  WorkerHistoryItem,
  WorkerOverviewItem,
  WorkerPaySummary,
} from '@/features/workers'
import type { WorkerItem } from '../domain/types'

export async function queryDepartmentWorkers(departmentCode: string) {
  const response = await service.get<{ data: WorkerItem[] }>(
    `/departments/${departmentCode}/workers`,
  )
  return response.data.data
}

export async function queryDepartmentWorkerOverview(departmentCode: string) {
  const response = await service.get<{ data: DepartmentWorkerOverview }>(
    `/departments/${departmentCode}/worker-overview`,
  )
  return response.data.data
}

export async function queryDepartmentWorkerHistory(
  departmentCode: string,
  workerId: number,
  month: string,
) {
  const response = await service.get<{ data: WorkerHistoryItem[] }>(
    `/departments/${departmentCode}/workers/${workerId}/work-history`,
    { params: { month } },
  )
  return response.data.data
}

export async function queryDepartmentWorkerPay(
  departmentCode: string,
  workerId: number,
  month: string,
) {
  const response = await service.get<{ data: WorkerPaySummary }>(
    `/departments/${departmentCode}/workers/${workerId}/pay`,
    { params: { month } },
  )
  return response.data.data
}

export async function createDepartmentWorker(
  departmentCode: string,
  workerName: string,
  workshopId: number | null,
) {
  const response = await service.post<{ data: WorkerOverviewItem }>(
    `/departments/${departmentCode}/workers`,
    {
      worker_name: workerName,
      workshop_id: workshopId,
    },
  )
  return response.data.data
}

export async function updateDepartmentWorker(
  departmentCode: string,
  workerId: number,
  workerName: string,
  workshopId: number | null,
) {
  const response = await service.put<{ data: WorkerOverviewItem }>(
    `/departments/${departmentCode}/workers/${workerId}`,
    { worker_name: workerName, workshop_id: workshopId },
  )
  return response.data.data
}

export async function deleteDepartmentWorker(departmentCode: string, workerId: number) {
  await service.delete(`/departments/${departmentCode}/workers/${workerId}`)
}
