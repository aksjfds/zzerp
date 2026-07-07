import { service } from '@/api/request'
import type {
  PendingQcBatch,
  ProductionObject,
  QcInspectionPayload,
  RepositoryItem,
  WorkOrder,
  WorkOrderBatch,
  WorkerItem,
} from '../domain/types'

export async function queryDepartmentProductionObjects(
  departmentCode: string,
  page = 1,
  pageSize = 50,
) {
  const response = await service.get<{ data: ProductionObject[]; total: number }>(
    `/departments/${departmentCode}/production-objects`,
    { params: { page, page_size: pageSize } },
  )
  return { items: response.data.data, total: response.data.total }
}

export async function queryDepartmentRepositories(departmentCode: string, page = 1, pageSize = 50) {
  const response = await service.get<{ data: RepositoryItem[]; total: number }>(
    `/departments/${departmentCode}/repositories`,
    { params: { page, page_size: pageSize } },
  )
  return { items: response.data.data, total: response.data.total }
}

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

export async function queryDepartmentWorkers(departmentCode: string) {
  const response = await service.get<{ data: WorkerItem[] }>(
    `/departments/${departmentCode}/workers`,
  )
  return response.data.data
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

export async function queryPendingQcBatches(
  page = 1,
  pageSize = 50,
  productionItemId?: number | null,
) {
  const response = await service.get<{ data: PendingQcBatch[]; total: number }>(
    '/qc/work-order-batches',
    { params: { page, page_size: pageSize, production_item_id: productionItemId || undefined } },
  )
  return { items: response.data.data, total: response.data.total }
}

export async function inspectQcBatch(batchId: number, payload: QcInspectionPayload) {
  const response = await service.post<{ data: WorkOrderBatch }>(
    `/qc/work-order-batches/${batchId}/inspection`,
    payload,
  )
  return response.data.data
}
