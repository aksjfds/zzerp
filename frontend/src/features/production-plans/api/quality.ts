import { service } from '@/api/request'

export type QualityRow = {
  id: number
  work_order_id: number
  source_ref: string
  order_no: string
  product: string
  material: string
  department: string
  quantity: string
  plan_status: string
  created_at: string
  actor_username: string
  note: string
  good_quantity: string
  scrap_quantity: string
  rework_quantity: string
  repair_department: string

}
export type InspectionBatch = Pick<QualityRow, 'id' | 'work_order_id' | 'order_no' | 'product' | 'material' | 'quantity'> & { source_kind: 'handoff' | 'return' | 'warehouse' }
export type InspectionInput = {
  source_kind: 'handoff' | 'return' | 'warehouse'
  source_id: number
  good_quantity: number
  scrap_quantity: number
  rework_quantity: number
  repair_department_code: string | null
  request_id: string
  note: string
}
export type RepairTarget = { code: string; label: string }
export type QualityEvent = {
  key: string
  kind: 'inspection' | 'receive' | 'return'
  round: number
  created_at: string
  actor_username: string
  department: string
  quantity: string
  ticket_no: string
  note: string
  repaired_quantity: string
  unrepaired_quantity: string
  inspection: QualityRow | null
}
export type QualityBatch = {
  id: number
  source_ref: string
  order_no: string
  product: string
  material: string
  quantity: string
  status: 'finished' | 'awaiting_repair_receipt' | 'repairing' | 'awaiting_reinspection'
  events: QualityEvent[]
}
export async function queryQuality(page: number) {
  return (await service.get<{ data: QualityBatch[]; total: number }>('/production-plans/qc/history', {
    params: { page, page_size: 20 },
  })).data
}
export async function queryRepairTargets(orderId: number) {
  return (await service.get<{ data: RepairTarget[] }>(`/production-plans/qc/orders/${orderId}/targets`)).data.data
}
export async function saveInspection(input: InspectionInput) {
  await service.post('/production-plans/qc/inspections', input)
}
export type ReworkInput = {
  action: 'receive' | 'return'
  quantity?: number
  repaired_quantity?: number
  unrepaired_quantity?: number
  request_id: string
  note: string
}
export async function saveRework(ticketId: number, input: ReworkInput) {
  await service.post(`/production-plans/qc/rework/${ticketId}/events`, input)
}
