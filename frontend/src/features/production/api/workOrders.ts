import { service } from '@/api/request'
import type { CompletionAction, WorkOrder } from '../domain/types'

export async function queryDepartmentWorkOrders(
  departmentCode: string,
  page = 1,
  pageSize = 50,
  productionItemId?: number | null,
  flowNodeId?: string | null,
  sourceFlowNodeId?: string | null,
  substepId?: number | null,
) {
  const response = await service.get<{ data: WorkOrder[]; total: number }>(
    `/departments/${departmentCode}/work-orders`,
    {
      params: {
        page,
        page_size: pageSize,
        production_item_id: productionItemId || undefined,
        flow_node_id: flowNodeId || undefined,
        source_flow_node_id: sourceFlowNodeId || undefined,
        substep_id: substepId || undefined,
      },
    },
  )
  return { items: response.data.data, total: response.data.total }
}

export async function createWorkOrder(
  repositoryId: number | null,
  procedureStageStockId: number | null,
  substepName: string,
  quantity: number,
  workerId: number | null,
) {
  if ((repositoryId === null) === (procedureStageStockId === null)) {
    throw new Error('工单来源必须且只能选择一种库存')
  }
  const source = procedureStageStockId === null
    ? { repository_id: repositoryId }
    : { procedure_stage_stock_id: procedureStageStockId }
  const response = await service.post<{ data: WorkOrder }>('/work-orders', {
    ...source,
    substep_name: substepName,
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

export async function cancelWorkOrder(workOrderId: number) {
  const response = await service.post<{ data: WorkOrder }>(
    `/work-orders/${workOrderId}/cancel`,
  )
  return response.data.data
}
