import { service } from '@/api/request'
import type {
  QcInspectionBatchRow,
  QcDestination,
  QcInspectionPayload,
  SupplierProcessingQcInspectionPayload,
  SupplierProcessingQcTask,
  WorkOrderBatch,
} from '../domain/types'
import type { ProductionProgressWorkOrder } from '../domain/productionProgress'

export async function queryQcInspectionBatches(
  page = 1,
  pageSize = 50,
  history = false,
  keyword = '',
) {
  const response = await service.get<{ data: QcInspectionBatchRow[]; total: number }>(
    '/qc/inspection-batches',
    {
      params: {
        page,
        page_size: pageSize,
        history,
        keyword: keyword || undefined,
      },
    },
  )
  return { items: response.data.data, total: response.data.total }
}

export async function queryQcWorkOrderDetail(workOrderId: number) {
  const response = await service.get<ProductionProgressWorkOrder>(
    `/qc/work-orders/${workOrderId}`,
  )
  return response.data
}

export async function inspectQcBatch(batchId: number, payload: QcInspectionPayload) {
  const response = await service.post<{ data: WorkOrderBatch }>(
    `/qc/work-order-batches/${batchId}/inspection`,
    payload,
  )
  return response.data.data
}

export async function undoQcInspection(batchId: number) {
  await service.post(`/qc/work-order-batches/${batchId}/inspection/undo`)
}

export async function decideQcDestination(batchId: number, destination: QcDestination) {
  const response = await service.post<{ data: WorkOrderBatch }>(
    `/qc/work-order-batches/${batchId}/destination`,
    { destination },
  )
  return response.data.data
}

export async function undoQcDestination(batchId: number) {
  await service.post(`/qc/work-order-batches/${batchId}/destination/undo`)
}

export async function querySupplierProcessingQcTasks(history = false) {
  const response = await service.get<{ data: SupplierProcessingQcTask[]; total: number }>(
    '/qc/supplier-processing-work-orders',
    { params: { history } },
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
