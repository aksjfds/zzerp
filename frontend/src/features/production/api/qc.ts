import { service } from '@/api/request'
import type {
  PendingQcBatch,
  QcDestination,
  QcInspectionPayload,
  SupplierProcessingQcInspectionPayload,
  SupplierProcessingQcTask,
  WorkOrderBatch,
} from '../domain/types'

export async function queryPendingQcBatches(
  page = 1,
  pageSize = 50,
  productionItemId?: number | null,
  history = false,
  keyword = '',
) {
  const response = await service.get<{ data: PendingQcBatch[]; total: number }>(
    '/qc/work-order-batches',
    {
      params: {
        page,
        page_size: pageSize,
        production_item_id: productionItemId || undefined,
        history,
        keyword: keyword || undefined,
      },
    },
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

export async function decideQcDestination(batchId: number, destination: QcDestination) {
  const response = await service.post<{ data: WorkOrderBatch }>(
    `/qc/work-order-batches/${batchId}/destination`,
    { destination },
  )
  return response.data.data
}

export async function querySupplierProcessingQcTasks() {
  const response = await service.get<{ data: SupplierProcessingQcTask[]; total: number }>(
    '/qc/supplier-processing-work-orders',
  )
  return { items: response.data.data, total: response.data.total }
}

export async function inspectSupplierProcessingWorkOrder(
  workOrderId: number,
  payload: SupplierProcessingQcInspectionPayload,
) {
  const response = await service.post<{ data: WorkOrderBatch }>(
    `/qc/supplier-processing-work-orders/${workOrderId}/inspections`,
    payload,
  )
  return response.data.data
}

export async function releaseSupplierProcessingBatch(batchId: number) {
  const response = await service.post<{ data: WorkOrderBatch }>(
    `/qc/supplier-processing-batches/${batchId}/release`,
  )
  return response.data.data
}
