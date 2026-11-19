import { service } from '@/api/request'

export type WarehouseStock = { id: number; arrival_date: string; product_id: number; material_key: string; product: string; material: string; available_quantity: string }
export type WarehousePick = {
  id: number; order_no: string; product: string; material: string; quantity: string
  department: string; actor_username: string; created_at: string; sources: string; note: string
}
export async function queryWarehouseStocks(page: number) {
  return (await service.get<{ data: WarehouseStock[]; total: number }>('/production-plans/warehouse/stocks', { params: { page, page_size: 50 } })).data
}
export async function queryWarehousePicks(page: number, pickId?: number) {
  return (await service.get<{ data: WarehousePick[]; total: number }>('/production-plans/warehouse/picks', { params: { page, page_size: 50, pick_id: pickId } })).data
}

export type WarehouseDispatchPlan = { id: number; order_no: string }
export type WarehouseDispatchTarget = { target_order_id: number; warehouse_order_id: number; department: string; material: string; available_quantity: string }
export async function queryDispatchPlans(lotId: number, keyword = '') {
  return (await service.get<{ data: WarehouseDispatchPlan[] }>(`/production-plans/warehouse/lots/${lotId}/dispatch-plans`, { params: { keyword: keyword || undefined } })).data.data
}
export async function queryDispatchTargets(lotId: number, planId: number) {
  return (await service.get<{ data: WarehouseDispatchTarget[] }>(`/production-plans/warehouse/lots/${lotId}/dispatch-targets`, { params: { plan_id: planId } })).data.data
}
export async function dispatchWarehouse(stock: WarehouseStock, target: WarehouseDispatchTarget, quantity: number, requestId: string, note: string) {
  return (await service.post<{ id: number }>(`/production-plans/warehouse/orders/${target.target_order_id}/dispatch`, {
    product_id: stock.product_id, material_key: stock.material_key, warehouse_order_id: target.warehouse_order_id,
    quantity, request_id: requestId, note,
  })).data
}

export async function queryDepartmentWarehouseStocks(page: number, departmentCode: string) {
  return (await service.get<{ data: WarehouseStock[]; total: number }>('/production-plans/warehouse/department-stocks', {
    params: { page, page_size: 50, department_code: departmentCode },
  })).data
}
