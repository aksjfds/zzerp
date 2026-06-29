export const DEPARTMENTS = ['in', 'laser', 'stamp', 'cnc', 'polish', 'qc', 'out'] as const
export type Department = (typeof DEPARTMENTS)[number]

export const DEPARTMENT_LABELS: Record<Department, string> = {
  in: '入库',
  laser: '激光',
  stamp: '冲压',
  cnc: 'CNC',
  polish: '磨房',
  qc: 'QC',
  out: '完工',
}

export type RepositoryStock = {
  id: number
  department: Department
  productId: number
  quantity: number
}

export type ProductItem = {
  id: number
  orderId: string
  zzCode: string
  productName: string
  deliveryDate: string
  process: Department[]
  quantity: number
  repositories: RepositoryStock[]
  createdAt: string
}

export type CreateProductPayload = {
  orderId: string
  zzCode: string
  productName: string
  deliveryDate: string
  process: Department[]
  quantity: number
}

export type ProductRecord = {
  id: number
  orderId: string
  zzCode: string
  product: string
  fromRepository: Department
  toRepository: Department
  quantity: number
  note?: string | null
  createdAt: string
}

export type WorkerItem = {
  id: number
  name: string
  department: Department
  active: boolean
}

export type ProcedureItem = {
  id: number
  procedureName: string
  department: Department
}

export type DepartmentProcessItem = {
  id: number
  productId: number
  department: Department
  sequenceNo: number
  processName: string
  requiresQc: boolean
  availableQuantity: number
}

export type ProcessStepPayload = {
  processName: string
  requiresQc: boolean
}

export type WorkOrderBatch = {
  id: number
  workOrderId: number
  batchNo: number
  submittedQuantity: number
  okQuantity: number | null
  reworkQuantity: number | null
  scrapQuantity: number | null
  lostQuantity: number | null
  qcWorkerId: number | null
  qcWorkerName?: string | null
  defectReason?: string | null
  status: 'pending_qc' | 'completed'
  submittedAt: string
  inspectedAt?: string | null
}

export type WorkOrderItem = {
  id: number
  workOrderNo: string
  productId: number
  orderId: string
  zzCode: string
  productName: string
  processId: number
  processName: string
  department: Department
  requiresQc: boolean
  workerId: number
  workerName: string
  issuedQuantity: number
  processingQuantity: number
  submittedQuantity: number
  pendingQcQuantity: number
  okQuantity: number
  reworkQuantity: number
  scrapQuantity: number
  lostQuantity: number
  status: 'open' | 'closed'
  note?: string | null
  createdAt: string
  closedAt?: string | null
  batches: WorkOrderBatch[]
}

export type PendingQcBatch = WorkOrderBatch & {
  workOrderNo: string
  orderId: string
  zzCode: string
  productName: string
  ownerDepartment: Department
  processName: string
  workerName: string
}

export type CreateWorkOrderPayload = {
  productId: number
  processId: number
  workerId: number
  quantity: number
  note?: string
}

export type DirectReportPayload = {
  okQuantity: number
  scrapQuantity: number
  lostQuantity: number
  reason?: string
}

export type InspectionPayload = {
  okQuantity: number
  reworkQuantity: number
  scrapQuantity: number
  lostQuantity: number
  defectReason?: string
}

export type AssignQcWorkerPayload = {
  qcWorkerId: number
}

export type CreateProcedurePayload = {
  department: Department
  procedureName: string
}
