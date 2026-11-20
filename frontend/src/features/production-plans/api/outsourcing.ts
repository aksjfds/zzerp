import { service } from '@/api/request'

export type OutsourceReturn = { id: number; quantity: string; actor_username: string; created_at: string; note: string }
export type OutsourceDispatch = OutsourceReturn & {
  process: 'etching' | 'plating'; vendor: string; returned_quantity: string; returns: OutsourceReturn[]
}
export type OutsourceReceipt = {
  id: number; order_no: string; product: string; material: string; plan_status: string
  quantity: string; dispatched_quantity: string; created_at: string; dispatches: OutsourceDispatch[]
}
export type OutsourceInput = { quantity: number; note: string; request_id: string }
export type OutsourceDispatchInput = OutsourceInput & { receipt_id: number; process: 'etching' | 'plating'; vendor: string }

export async function queryOutsourceReceipts(page: number, receiptId?: number) {
  return (await service.get<{ data: OutsourceReceipt[]; total: number }>('/production-plans/outsourcing/receipts', { params: { page, receipt_id: receiptId } })).data
}
export async function dispatchOutsource(input: OutsourceDispatchInput) {
  return (await service.post<{ id: number }>('/production-plans/outsourcing/dispatches', input)).data
}
export async function returnOutsource(id: number, input: OutsourceInput) {
  return (await service.post<{ id: number }>(`/production-plans/outsourcing/dispatches/${id}/returns`, input)).data
}
