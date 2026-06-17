export const PROCEDURE_OPTIONS = ['激光', 'CNC', '打磨', 'QC', '装配'] as const

export type ProcedureName = (typeof PROCEDURE_OPTIONS)[number]

export type WorkOrderStatus = '待开工' | '加工中' | '已完成'

export type OutboundRecord = {
  id: string
  quantity: number
  createdAt: string
  operator: string
}

export type ProcessStep = {
  name: ProcedureName
  inbound: number
  outbound: number
  outboundRecords: OutboundRecord[]
}

export type WorkOrderItem = {
  id: string
  part: string
  quantity: number
  status: WorkOrderStatus
  createdAt: string
  steps: ProcessStep[]
}

export type WorkOrderQuery = {
  orderId?: string
  part?: string
  status?: WorkOrderStatus | ''
  procedure?: ProcedureName | ''
}

export type CreateWorkOrderPayload = {
  part: string
  quantity: number
  procedures: ProcedureName[]
}
