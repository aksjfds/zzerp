import { service } from '@/api/request'
import type { CompletionAction, WorkOrder } from '../domain/types'

export async function queryDepartmentWorkOrders(
  departmentCode: string,
  page = 1,
  pageSize = 50,
  productionItemId?: number | null,
  flowNodeId?: string | null,
  sourceFlowNodeId?: string | null,
) {
  const params = new URLSearchParams()
  params.set('page', String(page))
  params.set('page_size', String(pageSize))
  if (productionItemId) params.set('production_item_id', String(productionItemId))
  if (flowNodeId) params.set('flow_node_id', flowNodeId)
  if (sourceFlowNodeId) params.set('source_flow_node_id', sourceFlowNodeId)
  const response = await service.get<{ data: WorkOrder[]; total: number }>(
    `/departments/${departmentCode}/work-orders`,
    { params },
  )
  return { items: response.data.data, total: response.data.total }
}

export async function createWorkOrder(
  repositoryId: number,
  procedureId: number | null,
  procedureName: string | null,
  quantity: number,
  workerId: number | null,
  remark: string,
) {
  const response = await service.post<{ data: WorkOrder }>('/work-orders', {
    repository_id: repositoryId,
    procedure_id: procedureId,
    procedure_name: procedureName,
    quantity,
    worker_id: workerId,
    remark,
  })
  return response.data.data
}

export async function createAssemblyWorkOrder(
  materials: Array<{ repository_id: number; quantity: number }>,
  procedureId: number | null,
  procedureName: string | null,
  quantity: number,
  workerId: number | null,
  remark: string,
) {
  const response = await service.post<{ data: WorkOrder }>('/assembly-work-orders', {
    materials,
    procedure_id: procedureId,
    procedure_name: procedureName,
    quantity,
    worker_id: workerId,
    remark,
  })
  return response.data.data
}

export async function submitWorkOrder(
  workOrderId: number,
  completionAction: CompletionAction,
) {
  const response = await service.post<{ data: WorkOrder }>(
    `/work-orders/${workOrderId}/submissions`,
    { completion_action: completionAction },
  )
  return response.data.data
}

export async function registerPurchaseArrival(workOrderId: number, quantity: number) {
  const response = await service.post<{ data: WorkOrder }>(
    `/work-orders/${workOrderId}/purchase-arrivals`,
    { quantity },
  )
  return response.data.data
}

export async function resubmitReworkBatch(batchId: number, quantity: number) {
  const response = await service.post<{ data: WorkOrder['batches'][number] }>(
    `/work-order-batches/${batchId}/rework-submissions`,
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

export async function undoProductionOperation(operationId: number) {
  const response = await service.post<{ data: WorkOrder }>(
    `/production-operations/${operationId}/undo`,
  )
  return response.data.data
}
