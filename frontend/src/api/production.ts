import type {
  AssignQcWorkerPayload,
  CreateProductPayload,
  CreateProcedurePayload,
  CreateReworkRequestPayload,
  CreateWorkOrderPayload,
  Department,
  DirectReportPayload,
  InspectionPayload,
  PendingQcBatch,
  PolishCleaningBatch,
  PolishProcessPreset,
  PolishProcessStep,
  PolishWorkerOverview,
  ProcedureItem,
  ProcessStepPayload,
  ProductDepartmentProgress,
  ProductItem,
  ProductRecord,
  ReworkRequestItem,
  WorkerItem,
  WorkOrderBatch,
  WorkOrderItem,
} from '@/types/production'
import { service } from './request'

export async function queryProducts(department?: Department) {
  const res = await service.get<{ data: ProductItem[] }>('/products', {
    params: { department },
  })
  return res.data.data
}

export async function queryProductDepartmentProgress(
  productId: number,
  department: Department,
) {
  const res = await service.get<{ data: ProductDepartmentProgress }>(
    `/products/${productId}/departments/${department}/progress`,
  )
  return res.data.data
}

export async function createProduct(payload: CreateProductPayload) {
  const res = await service.post<{ data: ProductItem }>('/products', {
    order_id: payload.orderId.trim(),
    zz_code: payload.zzCode.trim(),
    product_name: payload.productName.trim(),
    delivery_date: payload.deliveryDate,
    process: payload.process,
    quantity: payload.quantity,
  })
  return res.data.data
}

export async function queryProductRecords(
  orderId: string,
  zzCode: string,
  product: string,
  department?: Department,
) {
  const res = await service.get<{ data: ProductRecord[] }>('/records', {
    params: { order_id: orderId, zz_code: zzCode, product, department },
  })
  return res.data.data
}

export async function queryPolishProcesses(department: Department) {
  const res = await service.get<{ data: PolishProcessStep[] }>(
    `/work-orders/${department}/processes`,
  )
  return res.data.data
}

export async function configurePolishProcesses(
  department: Department,
  productId: number,
  steps: ProcessStepPayload[],
  presetId?: number,
) {
  const res = await service.post<{ data: PolishProcessStep[] }>(
    `/work-orders/${department}/processes`,
    {
      product_id: productId,
      preset_id: presetId,
      steps: steps.map((step) => ({
        process_name: step.processName.trim(),
        requires_cleaning: step.requiresCleaning,
        requires_qc: step.requiresQc,
      })),
    },
  )
  return res.data.data
}

export async function queryDepartmentWorkers(department: Department) {
  const res = await service.get<{ data: WorkerItem[] }>(`/work-orders/${department}/workers`)
  return res.data.data
}

export async function createDepartmentWorker(department: Department, name: string) {
  const res = await service.post<{ data: WorkerItem }>(`/work-orders/${department}/workers`, {
    name: name.trim(),
  })
  return res.data.data
}

export async function queryDepartmentProcedures(department: Department) {
  const res = await service.get<{ data: ProcedureItem[] }>(
    `/work-orders/${department}/procedures`,
  )
  return res.data.data
}

export async function createDepartmentProcedure(payload: CreateProcedurePayload) {
  const res = await service.post<{ data: ProcedureItem }>(
    `/work-orders/${payload.department}/procedures`,
    {
      department: payload.department,
      procedure_name: payload.procedureName.trim(),
    },
  )
  return res.data.data
}

export async function queryDepartmentWorkOrders(department: Department) {
  const res = await service.get<{ data: WorkOrderItem[] }>(`/work-orders/${department}`)
  return res.data.data
}

export async function queryPolishWorkerOverview(params: {
  startDate: string
  endDate: string
  workerId?: number
  productId?: number
  processName?: string
}) {
  const res = await service.get<{ data: PolishWorkerOverview[] }>(
    '/work-orders/polish/workers/overview',
    {
      params: {
        start_date: params.startDate,
        end_date: params.endDate,
        worker_id: params.workerId,
        product_id: params.productId,
        process_name: params.processName,
      },
    },
  )
  return res.data.data
}

export async function createWorkOrder(payload: CreateWorkOrderPayload) {
  const res = await service.post<{ data: WorkOrderItem }>('/work-orders', {
    product_id: payload.productId,
    department: payload.department,
    process_name: payload.processName,
    worker_id: payload.workerId,
    quantity: payload.quantity,
    rework_request_id: payload.reworkRequestId,
    note: payload.note?.trim() || undefined,
  })
  return res.data.data
}

export async function queryDepartmentReworkRequests(department: Department) {
  const res = await service.get<{ data: ReworkRequestItem[] }>(
    `/work-orders/${department}/rework-requests`,
  )
  return res.data.data
}

export async function createReworkRequest(payload: CreateReworkRequestPayload) {
  const res = await service.post<{ data: ReworkRequestItem }>(
    '/work-orders/rework-requests',
    {
      source_work_order_id: payload.sourceWorkOrderId,
      source_batch_id: payload.sourceBatchId,
      target_department: payload.targetDepartment,
      target_process_name: payload.targetProcessName.trim(),
      quantity: payload.quantity,
      reason: payload.reason.trim(),
    },
  )
  return res.data.data
}

export async function queryPolishProcessPresets() {
  const res = await service.get<{ data: PolishProcessPreset[] }>(
    '/work-orders/polish/presets',
  )
  return res.data.data
}

export async function savePolishProcessPreset(
  presetName: string,
  steps: ProcessStepPayload[],
  active: boolean,
  presetId?: number,
) {
  const payload = {
    preset_name: presetName.trim(),
    active,
    steps: steps.map((step) => ({
      process_name: step.processName.trim(),
      requires_cleaning: step.requiresCleaning,
      requires_qc: step.requiresQc,
    })),
  }
  const res = presetId
    ? await service.put<{ data: PolishProcessPreset }>(
        `/work-orders/polish/presets/${presetId}`,
        payload,
      )
    : await service.post<{ data: PolishProcessPreset }>('/work-orders/polish/presets', payload)
  return res.data.data
}

export async function createCleaningSubmission(workOrderId: number, quantity: number) {
  const res = await service.post<{ data: PolishCleaningBatch }>(
    `/work-orders/${workOrderId}/cleaning-submissions`,
    { quantity },
  )
  return res.data.data
}

export async function completeCleaningSubmission(cleaningBatchId: number) {
  const res = await service.post<{ data: PolishCleaningBatch }>(
    `/work-orders/cleaning-submissions/${cleaningBatchId}/complete`,
  )
  return res.data.data
}

export async function createWorkOrderSubmission(workOrderId: number, quantity: number) {
  const res = await service.post<{ data: WorkOrderBatch }>(
    `/work-orders/${workOrderId}/submissions`,
    { quantity },
  )
  return res.data.data
}

export async function createDirectReport(workOrderId: number, payload: DirectReportPayload) {
  const res = await service.post<{ data: WorkOrderBatch }>(
    `/work-orders/${workOrderId}/direct-reports`,
    {
      ok_quantity: payload.okQuantity,
      scrap_quantity: payload.scrapQuantity,
      lost_quantity: payload.lostQuantity,
      reason: payload.reason?.trim() || undefined,
    },
  )
  return res.data.data
}

export async function queryPendingQcSubmissions() {
  const res = await service.get<{ data: PendingQcBatch[] }>('/qc/submissions/pending')
  return res.data.data
}

export async function assignQcSubmission(
  batchId: number,
  payload: AssignQcWorkerPayload,
) {
  const res = await service.post<{ data: WorkOrderBatch }>(
    `/qc/submissions/${batchId}/assignment`,
    { qc_worker_id: payload.qcWorkerId },
  )
  return res.data.data
}

export async function inspectQcSubmission(batchId: number, payload: InspectionPayload) {
  const res = await service.post<{ data: WorkOrderBatch }>(
    `/qc/submissions/${batchId}/inspection`,
    {
      ok_quantity: payload.okQuantity,
      rework_quantity: payload.reworkQuantity,
      scrap_quantity: payload.scrapQuantity,
      lost_quantity: payload.lostQuantity,
      defect_reason: payload.defectReason?.trim() || undefined,
    },
  )
  return res.data.data
}
