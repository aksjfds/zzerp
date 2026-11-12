import { service } from '@/api/request'
import type { PlanAction, ProductionPlan, ProductionPlanInput } from '../domain/types'

export async function queryPlans(page = 1, pageSize = 50) {
  const response = await service.get<{ data: ProductionPlan[]; total: number }>('/production-plans', {
    params: { page, page_size: pageSize },
  })
  return response.data
}

export async function savePlan(input: ProductionPlanInput, plan?: ProductionPlan) {
  const response = plan
    ? await service.put<{ data: ProductionPlan }>(`/production-plans/${plan.id}`, {
        ...input, expected_revision: plan.revision,
      })
    : await service.post<{ data: ProductionPlan }>('/production-plans', input)
  return response.data.data
}

export async function changePlanStatus(plan: ProductionPlan, action: PlanAction) {
  const response = await service.post<{ data: ProductionPlan }>(
    `/production-plans/${plan.id}/${action}`, null,
    { params: { expected_revision: plan.revision } },
  )
  return response.data.data
}

export async function deletePlan(plan: ProductionPlan) {
  await service.delete(`/production-plans/${plan.id}`, {
    params: { expected_revision: plan.revision },
  })
}

export type PlanProduct = {
  id: number
  customer_id: number
  product_name: string
  factory_code: string
}

export async function queryPlanProducts(customerId: number, keyword = '') {
  const response = await service.get<{ data: PlanProduct[] }>('/products', {
    params: { customer_id: customerId, keyword: keyword || undefined, page: 1, page_size: 50 },
  })
  return response.data.data
}


export type DepartmentWorkOrder = {
  id: number
  production_plan_id: number
  material_node_id: string
  department_node_id: string
  order_no: string
  order_quantity: number
  customer_name: string
  product_id: number
  factory_code: string
  product_name: string
  part_no: string
  part_name: string
  department_code: string
  department_name: string
  task_quantity: number
  received_quantity: string
  issued_quantity: string
  plan_status: ProductionPlan['status']
}

export async function queryDepartmentWorkOrders(params: {
  page: number; department_code?: string; plan_id?: number
  order_no?: string; product_keyword?: string
}) {
  const response = await service.get<{ data: DepartmentWorkOrder[]; total: number }>(
    '/production-plans/department-work-orders', { params },
  )
  return response.data
}

export type DepartmentMovementInput = {
  direction: 'receipt' | 'issue'
  quantity: number
  note: string
  request_id: string
}

export type DepartmentMovement = DepartmentMovementInput & {
  id: number
  actor_username: string
  created_at: string
}

export async function recordDepartmentMovement(orderId: number, payload: DepartmentMovementInput) {
  const response = await service.post<{ data: DepartmentMovement }>(
    `/production-plans/department-work-orders/${orderId}/movements`, payload,
  )
  return response.data.data
}

export async function queryDepartmentMovements(orderId: number, page = 1) {
  const response = await service.get<{ data: DepartmentMovement[]; total: number }>(
    `/production-plans/department-work-orders/${orderId}/movements`, { params: { page, page_size: 50 } },
  )
  return response.data
}
