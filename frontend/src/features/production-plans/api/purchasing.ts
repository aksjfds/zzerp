import { service } from '@/api/request'
import type { DepartmentWorkOrder } from './plans'

export type PurchaseRecord = {
  id: number; quantity: string; note: string; actor_username: string; created_at: string
  received: boolean; received_quantity: string
}
export type PurchaseWorkOrder = DepartmentWorkOrder & { purchases: PurchaseRecord[] }
export type PurchaseInput = { quantity: number; note: string; request_id: string }
export async function queryPurchaseWorkOrders(page: number) {
  return (await service.get<{ data: PurchaseWorkOrder[]; total: number }>('/production-plans/purchasing/work-orders', { params: { page } })).data
}
export async function createPurchase(orderId: number, input: PurchaseInput) {
  await service.post(`/production-plans/purchasing/work-orders/${orderId}`, input)
}
export async function receivePurchase(purchaseId: number, input: PurchaseInput) {
  await service.post(`/production-plans/purchasing/${purchaseId}/receipts`, input)
}
