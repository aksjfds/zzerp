export type WorkOrderStatus = 'open' | 'closed' | 'cancelled'
export type QcDestination = 'return' | 'release' | 'inventory'

export type ProcedureOption = {
  id: number
  workshop_id: number
  department_name: string
  department_code: string
  procedure_name: string
}

export type ProductionPositionStorageCandidate = {
  key: string
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
  completion_status: string
  available_quantity: number
  position_version: string
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
  qualified_destination: QcDestination | null
  destination_decided_at: string | null
  destination_decided_by: string | null
  recorded_at: string | null
}

export type WorkOrder = {
  id: number
  work_order_no: string
  repository_id: number | null
  production_item_id: number
  procedure_id: number | null
  flow_node_id: string
  source_flow_node_id: string | null
  work_order_type: 'standard' | 'assembly' | 'supplier_processing'
  is_temporary: boolean
  supplier_name: string | null
  supplier_process_name: string | null
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
    operation_type: 'submission' | 'rework_submission'
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
  allowed_destinations: QcDestination[]
}

export type CompletionAction = 'direct' | 'qc'

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
}

export type SupplierProcessingQcTask = {
  production_plan_id: number
  production_plan_item_id: number
  production_item_id: number
  customer_order_item_id: number
  product_id: number
  product_version: number
  product_bom_id: number
  source_flow_node_id: string
  supplier_flow_node_id: string
  item_code: string
  item_name: string
  work_order_id: number
  work_order_no: string
  supplier_name: string
  supplier_process_name: string
  remark: string | null
  task_quantity: number
  inspected_quantity: number
  qualified_quantity: number
  rework_quantity: number
  scrap_quantity: number
  lost_quantity: number
  remaining_qualified_quantity: number
  pending_destination_quantity: number
  released_quantity: number
  status: WorkOrderStatus
  created_at: string
  batches: WorkOrderBatch[]
}

export type SupplierProcessingQcInspectionPayload = QcInspectionPayload
