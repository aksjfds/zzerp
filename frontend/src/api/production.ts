import type {
  AssignQcWorkerPayload,
  CreateProductPayload,
  CreateProcedurePayload,
  CreateWorkOrderPayload,
  Department,
  DepartmentProcessItem,
  DirectReportPayload,
  InspectionPayload,
  PendingQcBatch,
  ProcedureItem,
  ProcessStepPayload,
  ProductItem,
  ProductRecord,
  WorkerItem,
  WorkOrderBatch,
  WorkOrderItem,
} from '@/types/production'
import { service } from './request'

export async function queryProducts() {
  const res = await service.get<{ data: ProductItem[] }>('/products')
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

export async function queryDepartmentProcesses(department: Department) {
  const res = await service.get<{ data: DepartmentProcessItem[] }>(
    `/work-orders/${department}/processes`,
  )
  return res.data.data
}

export async function configureDepartmentProcesses(
  department: Department,
  productId: number,
  steps: ProcessStepPayload[],
) {
  const res = await service.post<{ data: DepartmentProcessItem[] }>(
    `/work-orders/${department}/processes`,
    {
      product_id: productId,
      steps: steps.map((step) => ({
        process_name: step.processName.trim(),
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

export async function createWorkOrder(payload: CreateWorkOrderPayload) {
  const res = await service.post<{ data: WorkOrderItem }>('/work-orders', {
    product_id: payload.productId,
    process_id: payload.processId,
    worker_id: payload.workerId,
    quantity: payload.quantity,
    note: payload.note?.trim() || undefined,
  })
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
