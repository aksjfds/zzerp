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
  workshop_name: string
  department_id: number
  department_name: string
  department_code: string
  quantity: number
  available_quantity: number
  assembly_unit_quantity: number
  assembly_required_source_ids: string[]
  assembly_group_complete: boolean
  delivery_date: string
  arrived_at: string | null
  work_status: 'unprocessed' | 'processing' | 'completed'
  can_create_work_order: boolean
  can_dispatch: boolean
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
}

export type RepositoryFilters = {
  keyword: string
  arrived_from: string | null
  arrived_to: string | null
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
  input_production_item_ids: number[]
  customer_order_no: string
  part_no: string
  part_name: string
  work_order_name: string
  worker_id: number | null
  worker_name: string | null
  quantity: number
  submitted_quantity: number
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
}

export type PendingQcBatch = WorkOrderBatch & {
  repository_id: number | null
  production_item_id: number
  work_order_no: string
  customer_order_no: string
  part_no: string
  part_name: string
  work_order_name: string
  remaining_quantity: number
}

export type CompletionAction = 'direct' | 'qc'

export type WorkOrderQueryScope = {
  flowNodeId: string
  sourceFlowNodeId: string
  targetTagSetId: number
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
