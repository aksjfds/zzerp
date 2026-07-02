export const DEPARTMENTS = [
  'in',
  'stamp',
  'cnc',
  'polish',
  'assembly',
  'finished',
  'qc',
  'out',
] as const
export type Department = (typeof DEPARTMENTS)[number]

export const FORMAL_DEPARTMENTS = [
  'stamp',
  'cnc',
  'polish',
  'assembly',
  'finished',
] as const satisfies readonly Department[]

export const DEPARTMENT_LABELS: Record<Department, string> = {
  in: '入库',
  stamp: '冲压',
  cnc: '机加',
  polish: '磨房',
  assembly: '装配',
  finished: '成品',
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

export type DepartmentProcessProgress = {
  id: number
  sequenceNo: number
  processName: string
  requiresCleaning: boolean
  requiresQc: boolean
  waitingQuantity: number
  issuedQuantity: number
  processingQuantity: number
  cleaningQuantity: number
  cleanedReadyQuantity: number
  pendingQcQuantity: number
  okQuantity: number
  reworkQuantity: number
  scrapQuantity: number
  lostQuantity: number
  progress: number
}

export type ProductDepartmentProgress = {
  productId: number
  orderId: string
  zzCode: string
  productName: string
  department: Department
  enteredQuantity: number
  currentQuantity: number
  processes: DepartmentProcessProgress[]
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

export type PolishProcessStep = {
  productId: number
  department: Department
  sequenceNo: number
  processName: string
  requiresCleaning: boolean
  requiresQc: boolean
  availableQuantity: number
}

export type PolishProcessPreset = {
  id: number
  presetName: string
  processFlow: string[]
  steps: ProcessStepPayload[]
  active: boolean
}

export type ProcessStepPayload = {
  processName: string
  requiresCleaning: boolean
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

export type PolishCleaningBatch = {
  id: number
  workOrderId: number
  batchNo: number
  quantity: number
  status: 'cleaning' | 'completed'
  sentAt: string
  completedAt?: string | null
}

export type WorkOrderItem = {
  id: number
  workOrderNo: string
  productId: number
  orderId: string
  zzCode: string
  productName: string
  processName: string
  department: Department
  requiresQc: boolean
  requiresCleaning: boolean
  workerId: number
  workerName: string
  issuedQuantity: number
  workOrderType: 'normal' | 'rework'
  reworkRequestId?: number | null
  processingQuantity: number
  cleaningQuantity: number
  cleanedReadyQuantity: number
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
  cleaningBatches: PolishCleaningBatch[]
}

export type PolishWorkerOrderOverview = {
  id: number
  workOrderNo: string
  productId: number
  orderId: string
  zzCode: string
  productName: string
  processName: string
  issuedQuantity: number
  okQuantity: number
  scrapQuantity: number
  lostQuantity: number
  completionRate: number
  scrapRate: number
  lostRate: number
  closedAt: string
}

export type PolishWorkerOverview = {
  workerId: number
  workerName: string
  workOrderCount: number
  issuedQuantity: number
  okQuantity: number
  scrapQuantity: number
  lostQuantity: number
  completionRate: number
  scrapRate: number
  lostRate: number
  orders: PolishWorkerOrderOverview[]
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
  department: Department
  processName: string
  workerId: number
  quantity: number
  reworkRequestId?: number
  note?: string
}

export type ReworkRequestItem = {
  id: number
  sourceWorkOrderId: number
  sourceWorkOrderNo: string
  sourceBatchId?: number | null
  productId: number
  orderId: string
  zzCode: string
  productName: string
  sourceDepartment: Department
  targetDepartment: Department
  targetProcessName: string
  quantity: number
  allocatedQuantity: number
  remainingQuantity: number
  returnedQuantity: number
  scrapQuantity: number
  lostQuantity: number
  reason: string
  status: 'pending' | 'processing' | 'closed'
  createdAt: string
  closedAt?: string | null
}

export type CreateReworkRequestPayload = {
  sourceWorkOrderId: number
  sourceBatchId?: number
  targetDepartment: Department
  targetProcessName: string
  quantity: number
  reason: string
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
