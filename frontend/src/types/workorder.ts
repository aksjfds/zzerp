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

export type OutboundRecord = {
  id: string
  quantity: number
  createdAt: string
  operator: string
}

export type ProcessStep = {
  name: Procedure
  inbound: number
  outbound: number
  // outboundRecords: OutboundRecord[]
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
