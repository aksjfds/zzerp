import { service } from '@/api/request'
import type { Operation } from './operations'
import type { PlanAction, PlanProductSnapshot, ProductionPlan, ProductionPlanInput } from '../domain/types'

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
  version_value: string
  version: number
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


export type WorkOrderComponent = {
  material_node_id: string
  part_no: string
  part_name: string
  required_quantity: string
  received_quantity: string
}

export type WorkOrderSchedule = {
  id: number
  scheduled_date: string | null
  schedule_revision: number
}

export async function saveWorkOrderSchedule(order: DepartmentWorkOrder, scheduledDate: string | null, orders?: WorkOrderSchedule[]) {
  const context = orders ?? (await service.get<{ data: WorkOrderSchedule[] }>(`/production-plans/department-work-orders/${order.id}/schedule-context`)).data.data
  const response = await service.put<{ data: WorkOrderSchedule[] }>(
    `/production-plans/department-work-orders/${order.id}/schedule`,
    { scheduled_date: scheduledDate, expected_revision: order.schedule_revision,
      expected_revisions: Object.fromEntries(context.map(item => [item.id, item.schedule_revision])) },
  )
  return response.data.data
}

export type DepartmentWorkOrder = WorkOrderSchedule & {
  department_occurrence: number
  upstream_departments: string[]
  downstream_departments: string[]
  can_issue: boolean
  requires_inspection: boolean
  good_quantity: string
  scrap_quantity: string
  rework_quantity: string
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
  can_receive: boolean
  task_quantity: number
  received_quantity: string
  issued_quantity: string
  plan_status: ProductionPlan['status']
  components: WorkOrderComponent[]
}

export async function queryDepartmentWorkOrders(params: {
  page: number; department_code?: string; plan_id?: number; work_order_id?: number
  order_no?: string; product_keyword?: string
}) {
  const response = await service.get<{ data: DepartmentWorkOrder[]; total: number }>(
    '/production-plans/department-work-orders', { params },
  )
  return response.data
}


export type ProgressProduct = {
  completed_quantity: string
  order_quantity: number
  task_quantity: number
  product_id: number
  factory_code: string
  product_name: string
  materials: {
    order_quantity: number
    task_quantity: number
    material_node_id: string
    part_no: string
    part_name: string
    work_orders: DepartmentWorkOrder[]
  }[]
}

export async function queryProductionProgress(params: { page: number; order_no?: string; product_keyword?: string }) {
  return (await service.get<{ data: ProgressPlan[]; total: number }>(
    '/production-plans/progress', { params: { ...params, page_size: 20 } },
  )).data
}

export type ProgressPlan = {
  production_plan_id: number
  order_no: string
  customer_name: string
  products: ProgressProduct[]
}

export type DepartmentMovementInput = {
  document_type?: 'normal' | 'piecework'
  worker_name?: string
  piecework_process?: string
  direction: 'receipt' | 'issue'
  quantity: number
  note: string
  request_id: string
  receipt_source: 'ticket' | 'warehouse' | null
  ticket_id: number | null
  warehouse_pick_id: number | null
  input_material_node_id: string | null
  target_work_order_id: number | null
}

export type DepartmentMovement = Omit<DepartmentMovementInput, 'receipt_source'> & {
  document_type: 'normal' | 'piecework'
  worker_name: string
  piecework_process: string
  receipt_source: 'external' | 'ticket' | 'warehouse' | null
  warehouse_pick_id: number | null
  source_department: string | null
  target_department: string | null
  id: number
  actor_username: string
  created_at: string
  ticket_no: string | null
  material_no: string
  material_name: string
}

export async function recordDepartmentMovement(orderId: number, payload: DepartmentMovementInput) {
  const response = await service.post<{ data: DepartmentMovement }>(
    `/production-plans/department-work-orders/${orderId}/movements`, payload,
  )
  return response.data.data
}

export async function queryDepartmentMovements(orderId: number, page = 1, inputMaterialNodeId?: string) {
  const response = await service.get<{ data: DepartmentMovement[]; total: number }>(
    `/production-plans/department-work-orders/${orderId}/movements`,
    { params: { page, page_size: 50, input_material_node_id: inputMaterialNodeId } },
  )
  return response.data
}

export type DepartmentLedgerMovement = DepartmentMovement & {
  kind?: 'movement'
  order_no: string; factory_code: string; product_name: string; department_name: string
}
export type DepartmentLedgerRecord = Operation & {
  counterpart: string; can_revoke: boolean; revoke_blocker: string | null; movement: DepartmentLedgerMovement | null
}
export async function queryDepartmentLedger(page: number, departmentCode?: string) {
  return (await service.get<{ data: DepartmentLedgerRecord[]; total: number }>(
    '/production-plans/department-movements', { params: { page, page_size: 50, department_code: departmentCode } },
  )).data
}

export type HandoffOptions = {
  available_issue_quantity: string | null
  can_receive: boolean
  targets: { id: number; label: string; department_name: string; can_piecework: boolean }[]
}
export type HandoffTicket = {
  outsource_available_quantity: string | null
  outsource_pending_return: boolean
  document_type: 'normal' | 'piecework'
  worker_name: string
  piecework_process: string
  kind: 'normal' | 'rework' | 'return' | 'warehouse'
  action: 'none' | 'receive' | 'inspect' | 'rework_receive' | 'rework_return' | 'outsource'
  receipt_id: number | null
  can_receive: boolean
  id: number; ticket_no: string; order_no: string; material_no: string; material_name: string
  factory_code: string; product_name: string
  source_department: string; target_department: string; quantity: number; received_quantity: string
  created_at: string; note: string; target_work_order_id: number | null; plan_status: ProductionPlan['status']
}
export async function queryHandoffOptions(orderId: number) {
  return (await service.get<HandoffOptions>(`/production-plans/department-work-orders/${orderId}/handoff-options`)).data
}
export async function queryHandoffTickets(params: { page: number; unreceived: boolean; order_no?: string; department_code?: string; direction?: 'incoming' | 'outgoing' }) {
  return (await service.get<{ data: HandoffTicket[]; total: number }>('/production-plans/handoff-tickets', { params })).data
}


export async function queryPlanProductSnapshot(planId: number, productId: number) {
  const response = await service.get<{ data: PlanProductSnapshot }>(
    `/production-plans/${planId}/products/${productId}/snapshot`,
  )
  return response.data.data
}
