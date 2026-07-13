import { service } from '@/api/request'
import type { WorkOrder } from '../domain/types'

export async function queryDepartmentWorkOrders(
  departmentCode: string,
  page = 1,
  pageSize = 50,
  productionItemId?: number | null,
) {
  const response = await service.get<{ data: WorkOrder[]; total: number }>(
    `/departments/${departmentCode}/work-orders`,
    { params: { page, page_size: pageSize, production_item_id: productionItemId || undefined } },
  )
  return { items: response.data.data, total: response.data.total }
}

export async function createWorkOrder(
  repositoryId: number,
  quantity: number,
  workerId: number | null,
) {
  const response = await service.post<{ data: WorkOrder }>('/work-orders', {
    repository_id: repositoryId,
    quantity,
    worker_id: workerId,
  })
  return response.data.data
}

export async function createAssemblyWorkOrder(
  repositoryIds: number[],
  quantity: number,
  workerId: number | null,
) {
  const response = await service.post<{ data: WorkOrder }>('/assembly-work-orders', {
    repository_ids: repositoryIds,
    quantity,
    worker_id: workerId,
  })
  return response.data.data
}

export async function submitWorkOrder(workOrderId: number, quantity: number) {
  const response = await service.post<{ data: WorkOrder }>(
    `/work-orders/${workOrderId}/submissions`,
    { quantity },
  )
  return response.data.data
}

export async function cancelWorkOrder(workOrderId: number) {
  const response = await service.post<{ data: WorkOrder }>(
    `/work-orders/${workOrderId}/cancel`,
  )
  return response.data.data
}
