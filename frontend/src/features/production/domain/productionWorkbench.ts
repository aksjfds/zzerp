import type { ProcedureOption } from './types'

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

export type ProductionWorkbenchPositionQuery = {
  page: number
  page_size: number
  customer_order_item_id: number
  workshop_id: number
  flow_node_id: string
  production_item_id?: number
}
