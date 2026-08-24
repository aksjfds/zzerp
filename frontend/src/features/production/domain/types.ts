export type RepositoryWorkStatus =
  | 'unprocessed'
  | 'processing'
  | 'processing_completed'
  | 'qc'
  | 'rework'
  | 'completed'
export type WorkOrderStatus = 'open' | 'closed' | 'cancelled'
export type QcDisposition = 'return' | 'release'

export type ProcedureOption = {
  id: number
  workshop_id: number
  department_name: string
  department_code: string
  procedure_name: string
  procedure_type: 'standard' | 'purchase_receipt'
  input_mode: 'single' | 'multiple'
}

export type RepositoryItem = {
  card_key: string
  repository_id: number | null
  production_item_id: number
  customer_order_item_id: number
  customer_order_no: string
  customer_name: string
  product_id: number
  product_version: number
  product_name: string
  factory_code: string
  product_bom_id: number | null
  part_name: string
  part_no: string
  flow_node_id: string
  node_type: string
  source_flow_node_id: string
  source_node_label: string
  material_source_name: string
  workshop_id: number
  available_procedures: ProcedureOption[]
  workshop_name: string
  department_id: number
  department_name: string
  department_code: string
  quantity: number
  available_quantity: number
  assembly_unit_quantity: number
  assembly_required_source_ids: string[]
  assembly_material_key: string
  assembly_required_material_keys: string[]
  assembly_group_complete: boolean
  assembly_output_name: string | null
  delivery_date: string
  arrived_at: string | null
  work_status: RepositoryWorkStatus
  can_create_work_order: boolean
}

export type DepartmentSurplusInventoryItem = {
  key: string
  source_kind: 'production' | 'qc'
  batch_id: number | null
  production_item_id: number
  customer_order_no: string
  product_code: string
  product_name: string
  product_version: number
  item_type: 'part' | 'assembly'
  item_code: string
  item_name: string
  department_code: string
  flow_node_id: string
  source_flow_node_id: string
  current_node_label: string
  completed_flow_node_id: string
  completed_node_label: string
  quantity: number
}

export type RepositoryFilters = {
  keyword: string
  workshop_name: string | null
  work_status: 'all' | RepositoryWorkStatus
}

export type WorkOrderBatch = {
  id: number
  work_order_id: number
  submitted_quantity: number
  source_flow_node_id: string
  rework_source_batch_id: number | null
  rework_pending_quantity: number
  qualified_quantity: number | null
  rework_quantity: number | null
  scrap_quantity: number | null
  lost_quantity: number | null
  qc_worker_id: number | null
  qc_worker_name: string | null
  defect_reason: string | null
  qualified_disposition: QcDisposition | null
  recorded_at: string | null
}

export type WorkOrder = {
  id: number
  work_order_no: string
  repository_id: number | null
  production_item_id: number
  procedure_id: number
  flow_node_id: string
  source_flow_node_id: string | null
  work_order_type: 'standard' | 'purchase_receipt' | 'assembly'
  qc_available: boolean
  direct_result_allowed: boolean
  input_production_item_ids: number[]
  customer_order_no: string
  factory_code: string
  product_name: string
  part_no: string
  part_name: string
  procedure_name: string
  work_order_name: string
  created_by: string
  remark: string
  worker_id: number | null
  worker_name: string | null
  quantity: number
  output_unit_quantity: number
  output_quantity: number
  processed_quantity: number
  submitted_quantity: number
  ready_for_qc_quantity: number
  processing_quantity: number
  processing_output_quantity: number
  ready_output_quantity: number
  pending_qc_quantity: number
  qualified_quantity: number
  qualified_output_quantity: number
  rework_quantity: number
  scrap_quantity: number
  lost_quantity: number
  status: WorkOrderStatus
  created_at: string
  closed_at: string | null
  batches: WorkOrderBatch[]
  undo_operation: {
    id: number
    work_order_batch_id: number | null
    operation_type: 'purchase_arrival' | 'submission' | 'rework_submission'
    operation_label: string
    actor_username: string
    created_at: string
  } | null
}

export type PendingQcBatch = WorkOrderBatch & {
  repository_id: number | null
  production_item_id: number
  work_order_no: string
  customer_order_no: string
  part_no: string
  part_name: string
  work_order_name: string
}

export type CompletionAction = 'direct' | 'qc'

export type WorkOrderQueryScope = {
  flowNodeId: string
  sourceFlowNodeId: string
}

export type WorkerItem = {
  id: number
  worker_name: string
  department_id: number
  workshop_id: number | null
}

export type QcInspectionPayload = {
  qc_worker_id: number
  qualified_quantity: number
  rework_quantity: number
  scrap_quantity: number
  lost_quantity: number
  defect_reason: string
  qualified_disposition: QcDisposition | null
}
