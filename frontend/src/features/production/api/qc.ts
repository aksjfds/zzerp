import { service } from '@/api/request'
import type {
  PendingQcBatch,
  QcInspectionPayload,
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

export async function dispatchQcBatch(batchId: number, quantity: number) {
  await service.post(`/qc/work-order-batches/${batchId}/dispatch`, { quantity })
}

export async function storeQcBatchInWarehouse(batchId: number, quantity: number) {
  return (await service.post<{
    quantity: number
    completed_node_label: string
  }>(`/qc/work-order-batches/${batchId}/warehouse-storage`, { quantity })).data
}
