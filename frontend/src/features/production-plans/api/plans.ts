import { service } from '@/api/request'
import type { Page } from '@/shared/query/types'
import type {
  PlanAction, ProductionPlan, ProductionPlanInput, PlanProduct,
  DepartmentWorkOrder, ProgressPlan, DepartmentMovementInput, DepartmentMovement,
  DepartmentLedgerMovement, HandoffOptions, HandoffTicket,
} from '../domain/types'

export async function queryPlans(page = 1, pageSize = 50, signal?: AbortSignal) {
  return (await service.get<Page<ProductionPlan>>('/production-plans', {
    params: { page, page_size: pageSize }, signal,
  })).data
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
  return (await service.post<{ data: ProductionPlan }>(
    `/production-plans/${plan.id}/${action}`, null,
    { params: { expected_revision: plan.revision } },
  )).data.data
}

export async function deletePlan(plan: ProductionPlan) {
  await service.delete(`/production-plans/${plan.id}`, {
    params: { expected_revision: plan.revision },
  })
}

export async function queryPlanProducts(customerId: number, keyword = '', signal?: AbortSignal) {
  return (await service.get<{ data: PlanProduct[] }>('/products/options', {
    params: { customer_id: customerId, keyword: keyword || undefined }, signal,
  })).data.data
}

export async function queryDepartmentWorkOrders(params: {
  page: number; department_code?: string; plan_id?: number; work_order_id?: number
  order_no?: string; product_keyword?: string
}, signal?: AbortSignal) {
  return (await service.get<Page<DepartmentWorkOrder>>(
    '/production-plans/department-work-orders', { params, signal },
  )).data
}

export async function queryProductionProgress(
  params: { page: number; order_no?: string; product_keyword?: string }, signal?: AbortSignal,
) {
  return (await service.get<Page<ProgressPlan>>(
    '/production-plans/progress', { params: { ...params, page_size: 20 }, signal },
  )).data
}

export async function recordDepartmentMovement(orderId: number, payload: DepartmentMovementInput) {
  return (await service.post<{ data: DepartmentMovement }>(
    `/production-plans/department-work-orders/${orderId}/movements`, payload,
  )).data.data
}

export async function queryDepartmentMovements(
  orderId: number, page = 1, inputMaterialNodeId?: string, signal?: AbortSignal,
) {
  return (await service.get<Page<DepartmentMovement>>(
    `/production-plans/department-work-orders/${orderId}/movements`,
    { params: { page, page_size: 50, input_material_node_id: inputMaterialNodeId }, signal },
  )).data
}

export async function queryDepartmentLedger(page: number, departmentCode?: string, signal?: AbortSignal) {
  return (await service.get<Page<DepartmentLedgerMovement>>(
    '/production-plans/department-movements',
    { params: { page, page_size: 50, department_code: departmentCode }, signal },
  )).data
}

export async function queryHandoffOptions(orderId: number, signal?: AbortSignal) {
  return (await service.get<HandoffOptions>(
    `/production-plans/department-work-orders/${orderId}/handoff-options`, { signal },
  )).data
}

export async function queryHandoffTickets(params: {
  page: number; unreceived: boolean; order_no?: string; department_code?: string
}, signal?: AbortSignal) {
  return (await service.get<Page<HandoffTicket>>('/production-plans/handoff-tickets', { params, signal })).data
}
