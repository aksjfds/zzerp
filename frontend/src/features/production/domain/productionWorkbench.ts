import type { ProcedureOption, WorkOrder } from './types'

export type ProductionWorkbenchWorkshop = {
  id: number
  department_id: number
  workshop_name: string
}

export type ProductionWorkbenchAttention =
  | 'all'
  | 'available'
  | 'processing'
  | 'ready_for_result'
  | 'qc'
  | 'rework'

export type WorkbenchActivity = {
  open_work_order_count: number
  processing_work_order_count: number
  ready_for_result_work_order_count: number
  pending_qc_work_order_count: number
  rework_work_order_count: number
}

export type StandardWorkbenchSource = {
  repository_id: number
  production_item_id: number
  source_work_order_id: number | null
  on_hand_quantity: number
  reserved_quantity: number
  available_quantity: number
  arrived_at: string | null
  available_procedures: ProcedureOption[]
  procedure_configuration_confirmed: boolean
  can_create_work_order: boolean
}

export type WorkbenchInventorySource = {
  repository_id: number
  production_item_id: number
  source_work_order_id: number | null
  on_hand_quantity: number
  reserved_quantity: number
  available_quantity: number
  arrived_at: string | null
}

export type AssemblyWorkbenchInputMaterial = {
  material_key: string
  item_code: string
  item_name: string
  unit_quantity: number
  on_hand_quantity: number
  reserved_quantity: number
  available_quantity: number
  allocated_quantity: number
  sources: WorkbenchInventorySource[]
}

export type AssemblyWorkbenchContinuationSource = WorkbenchInventorySource & {
  available_procedures: ProcedureOption[]
  procedure_configuration_confirmed: boolean
  can_create_work_order: boolean
}

export type StandardWorkbenchPosition = {
  position_key: string
  position_type: 'standard'
  production_item_id: number
  customer_order_item_id: number
  customer_order_no: string
  customer_name: string
  product_id: number
  product_version: number
  factory_code: string
  product_name: string
  item_code: string
  item_name: string
  flow_node_id: string
  source_flow_node_id: string
  source_node_label: string
  node_type: string
  workshop_id: number
  workshop_name: string
  department_id: number
  department_name: string
  department_code: string
  delivery_date: string
  arrived_at: string | null
  last_activity_at: string | null
  activity: WorkbenchActivity
  can_create_work_order: boolean
  on_hand_quantity: number
  reserved_quantity: number
  available_quantity: number
  source_count: number
  sources: StandardWorkbenchSource[]
}

export type AssemblyWorkbenchPosition = {
  position_key: string
  position_type: 'assembly'
  production_item_id: number | null
  customer_order_item_id: number
  customer_order_no: string
  customer_name: string
  product_id: number
  product_version: number
  factory_code: string
  product_name: string
  item_code: string
  item_name: string
  flow_node_id: string
  source_flow_node_id: null
  source_node_label: null
  node_type: string
  workshop_id: number
  workshop_name: string
  department_id: number
  department_name: string
  department_code: string
  delivery_date: string
  arrived_at: string | null
  last_activity_at: string | null
  activity: WorkbenchActivity
  can_create_work_order: boolean
  capacity_quantity: number
  initial_capacity_quantity: number
  continuation_capacity_quantity: number
  input_materials_complete: boolean
  can_create_initial_work_order: boolean
  input_material_count: number
  input_materials: AssemblyWorkbenchInputMaterial[]
  continuation_sources: AssemblyWorkbenchContinuationSource[]
  available_procedures: ProcedureOption[]
  procedure_configuration_confirmed: boolean
}

export type ProductionWorkbenchPosition =
  | StandardWorkbenchPosition
  | AssemblyWorkbenchPosition

export type ProductionWorkbenchProcedureSummary = {
  procedure_id: number
  procedure_name: string
  is_temporary: boolean
  work_order_count: number
  open_work_order_count: number
  work_order_quantity: number
  processing_quantity: number
  ready_for_result_quantity: number
  pending_qc_quantity: number
  qualified_quantity: number
  rework_quantity: number
  scrap_quantity: number
  lost_quantity: number
}

export type ProductionWorkbenchInputMaterial = {
  production_item_id: number
  item_code: string
  item_name: string
  quantity: number
  source_completion: string
  source_work_order_no: string | null
}

export type ProductionWorkbenchWorkOrder = WorkOrder & {
  input_materials: ProductionWorkbenchInputMaterial[]
}

export type ProductionWorkbenchWorkOrders = {
  items: ProductionWorkbenchWorkOrder[]
  total: number
  procedureSummaries: ProductionWorkbenchProcedureSummary[]
}

export type ProductionWorkbenchPositionQuery = {
  page: number
  page_size: number
  keyword?: string
  workshop_name?: string
  attention: ProductionWorkbenchAttention
}

export type StandardWorkbenchWorkOrderQuery = {
  position_type: 'standard'
  page: number
  page_size: number
  production_item_id: number
  flow_node_id: string
  source_flow_node_id: string
  procedure_id?: number
  is_temporary?: boolean
}

export type AssemblyWorkbenchWorkOrderQuery = {
  position_type: 'assembly'
  page: number
  page_size: number
  customer_order_item_id: number
  flow_node_id: string
  procedure_id?: number
  is_temporary?: boolean
}

export type ProductionWorkbenchWorkOrderQuery =
  | StandardWorkbenchWorkOrderQuery
  | AssemblyWorkbenchWorkOrderQuery
