export type ProcedureTag = {
  id: number
  procedure_id: number
  tag_name: string
}

export type RepositoryItem = {
  card_key: string
  repository_id: number | null
  tag_stock_id: number | null
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
  source_flow_node_id: string
  source_node_label: string
  procedure_id: number | null
  procedure_name: string
  current_tag_set_name: string | null
  available_tags: ProcedureTag[]
  configured_tags: ProcedureTag[]
  workshop_name: string
  department_id: number
  department_name: string
  department_code: string
  quantity: number
  available_quantity: number
  assembly_unit_quantity: number
  assembly_required_source_ids: string[]
  assembly_group_complete: boolean
  assembly_output_name: string | null
  delivery_date: string
  arrived_at: string | null
  work_status: 'unprocessed' | 'processing' | 'completed'
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

export type TagCard = {
  card_key: string
  production_item_id: number
  flow_node_id: string
  source_flow_node_id: string
  procedure_id: number
  tag_set_id: number | null
  tag_ids: number[]
  tag_names: string[]
  tag_set_name: string
  repository_id: number | null
  tag_stock_id: number | null
  available_quantity: number
  processing_quantity: number
  pending_qc_quantity: number
  completed_quantity: number
  processing_details: Array<{
    tag_names: string[]
    tag_set_name: string
    quantity: number
  }>
  can_create_work_order: boolean
}

export type ProductionOverviewRow = {
  name: string
  quantity: number
}

export type ProductionOverviewSummary = {
  pendingQuantity: number
  processingRows: ProductionOverviewRow[]
  pendingQcRows: ProductionOverviewRow[]
  completedRows: ProductionOverviewRow[]
}

export type RepositoryFilters = {
  keyword: string
  workshop_name: string | null
  work_status: 'all' | 'unprocessed' | 'processing' | 'completed'
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
  recorded_at: string | null
}

export type WorkOrder = {
  id: number
  work_order_no: string
  repository_id: number | null
  procedure_tag_stock_id: number | null
  production_item_id: number
  procedure_id: number | null
  flow_node_id: string
  source_flow_node_id: string | null
  applied_tag_set_id: number | null
  source_tag_set_id: number | null
  target_tag_set_id: number | null
  work_order_type: 'tag' | 'purchase_receipt' | 'assembly'
  qc_required: boolean
  input_production_item_ids: number[]
  customer_order_no: string
  factory_code: string
  product_name: string
  part_no: string
  part_name: string
  procedure_name: string
  work_order_name: string
  remark: string
  worker_id: number | null
  worker_name: string | null
  quantity: number
  processed_quantity: number
  submitted_quantity: number
  ready_for_qc_quantity: number
  processing_quantity: number
  pending_qc_quantity: number
  qualified_quantity: number
  rework_quantity: number
  scrap_quantity: number
  lost_quantity: number
  status: 'open' | 'closed' | 'cancelled'
  created_at: string
  closed_at: string | null
  batches: WorkOrderBatch[]
  undo_operation: {
    id: number
    work_order_batch_id: number | null
    operation_type: 'processing_completion' | 'submission' | 'rework_submission'
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
  dispatchable_quantity: number
  target_node_label: string | null
}

export type CompletionAction = 'direct' | 'qc'

export type WorkOrderQueryScope = {
  flowNodeId: string
  sourceFlowNodeId: string
  existingTagIds: number[]
  applyingTagIds: number[]
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
}
