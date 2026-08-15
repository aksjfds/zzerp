import { service } from '@/api/request'
import type { CompletionAction, WorkOrder } from '../domain/types'

export async function queryDepartmentWorkOrders(
  departmentCode: string,
  page = 1,
  pageSize = 50,
  productionItemId?: number | null,
  flowNodeId?: string | null,
  sourceFlowNodeId?: string | null,
  existingTagIds: number[] = [],
  applyingTagIds: number[] = [],
) {
  const params = new URLSearchParams()
  params.set('page', String(page))
  params.set('page_size', String(pageSize))
  if (productionItemId) params.set('production_item_id', String(productionItemId))
  if (flowNodeId) params.set('flow_node_id', flowNodeId)
  if (sourceFlowNodeId) params.set('source_flow_node_id', sourceFlowNodeId)
  existingTagIds.forEach(id => params.append('existing_tag_id', String(id)))
  applyingTagIds.forEach(id => params.append('applying_tag_id', String(id)))
  const response = await service.get<{ data: WorkOrder[]; total: number }>(
    `/departments/${departmentCode}/work-orders`,
    { params },
  )
  return { items: response.data.data, total: response.data.total }
}

export async function createWorkOrder(
  repositoryId: number | null,
  procedureTagStockId: number | null,
  tagNames: string[],
  quantity: number,
  workerId: number | null,
  remark: string,
) {
  if ((repositoryId === null) === (procedureTagStockId === null)) {
    throw new Error('工单来源必须且只能选择一种库存')
  }
  const source = procedureTagStockId === null
    ? { repository_id: repositoryId }
    : { procedure_tag_stock_id: procedureTagStockId }
  const response = await service.post<{ data: WorkOrder }>('/work-orders', {
    ...source,
    tag_names: tagNames,
    quantity,
    worker_id: workerId,
    remark,
  })
  return response.data.data
}

export async function createAssemblyWorkOrder(
  repositoryIds: number[],
  quantity: number,
  workerId: number | null,
  remark: string,
) {
  const response = await service.post<{ data: WorkOrder }>('/assembly-work-orders', {
    repository_ids: repositoryIds,
    quantity,
    worker_id: workerId,
    remark,
  })
  return response.data.data
}

export async function submitWorkOrder(
  workOrderId: number,
  quantity: number,
  completionAction: CompletionAction,
) {
  const response = await service.post<{ data: WorkOrder }>(
    `/work-orders/${workOrderId}/submissions`,
    {
      quantity,
      completion_action: completionAction,
    },
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
