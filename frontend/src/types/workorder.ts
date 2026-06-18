export const PROCEDURE_OPTIONS = ['laser', 'stamp', 'cnc', 'polish', 'qc'] as const

export type Procedure = (typeof PROCEDURE_OPTIONS)[number]

export const PROCEDURE_LABELS: Record<Procedure, string> = {
  laser: '激光',
  stamp: '冲压',
  cnc: 'CNC',
  polish: '打磨',
  qc: 'QC',
}

export type WorkOrderStatus = '待开工' | '加工中' | '已完成'

export type OperationRecord = {
  id: number
  quantity: number
  createdAt: string
  fromRepository?: Procedure | 'in' | null
  toRepository?: Procedure | 'out' | null
  worker?: string | null
  operator?: string | null
  note?: string | null
}

export type ProcessStep = {
  name: Procedure
  quantity: number
}

export type WorkOrderItem = {
  id: string
  item: string
  quantity: number
  status: WorkOrderStatus
  createdAt?: string
  steps: ProcessStep[]
}

export type WorkOrderQuery = {
  orderId?: string
  item?: string
  status?: WorkOrderStatus | ''
  procedure?: Procedure | ''
}

export type CreateWorkOrderPayload = {
  item: string
  quantity: number
  procedures: Procedure[]
}

export type MoveRepositoryQuantityPayload = {
  orderId: string
  item: string
  repository: Procedure
  quantity: number
  operator?: string
  worker?: string
  note?: string
}
