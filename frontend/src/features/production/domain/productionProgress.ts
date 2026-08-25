import type { ProductionPlanStatus } from '@/features/customer-orders'
import type { WorkOrderStatus } from './types'

export type ProductionProgressCardStatus =
  | 'not_arrived'
  | 'ready'
  | 'processing'
  | 'pending_qc'
  | 'completed'
  | 'exception'

export type DepartmentProductionProgressItem = {
  production_plan_item_id: number
  production_item_id: number | null
  flow_node_id: string | null
  part_no: string
  part_name: string
  processing_workshop: string
  task_quantity: number
  arrived_quantity: number
  material_arrivals: AssemblyMaterialArrival[]
  completed_quantity: number
  remark: string
}

export type AssemblyMaterialArrival = {
  material_type: 'part' | 'assembly'
  material_no: string
  material_name: string
  task_quantity: number
  arrived_quantity: number
}

export type ProductionProgressWorkOrder = {
  id: number
  work_order_no: string
  worker_name: string | null
  quantity: number
  processed_quantity: number
  submitted_quantity: number
  pending_qc_quantity: number
  completed_quantity: number
  rework_quantity: number
  scrap_quantity: number
  lost_quantity: number
  status: WorkOrderStatus
  created_at: string
  closed_at: string | null
}

export type ProductionProgressProcedureCard = {
  card_key: string
  card_type: 'process' | 'assembly'
  sort_order: number
  flow_node_id: string
  procedure_id: number | null
  card_name: string
  department_code: string
  department_name: string
  workshop_name: string
  procedure_name: string
  status: ProductionProgressCardStatus
  task_quantity: number
  arrived_quantity: number
  processing_quantity: number
  ready_for_qc_quantity: number
  pending_qc_quantity: number
  completed_quantity: number
  rework_quantity: number
  scrap_quantity: number
  lost_quantity: number
  work_orders: ProductionProgressWorkOrder[]
}

export type ProductionProgressItemDetail = {
  production_plan_item_id: number
  production_item_ids: number[]
  customer_order_no: string
  factory_code: string
  product_name: string
  part_no: string
  part_name: string
  plan_status: ProductionPlanStatus
  task_quantity: number
  cards: ProductionProgressProcedureCard[]
}
