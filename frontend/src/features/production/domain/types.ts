export type ProcedureSubstep = {
  id: number
  procedure_id: number
  substep_name: string
}

export type RepositoryItem = {
  card_key: string
  repository_id: number | null
  stage_stock_id: number | null
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
  completed_substep_id: number | null
  current_stage_name: string | null
  available_substeps: ProcedureSubstep[]
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

export type SubstepOpenWorkOrder = {
  id: number
  work_order_no: string
  worker_id: number | null
  processing_quantity: number
  worker_name: string | null
  quantity: number
}

export type SubstepCard = {
  card_key: string
  production_item_id: number
  flow_node_id: string
  source_flow_node_id: string
  procedure_id: number
  substep_id: number | null
  substep_name: string
  repository_id: number | null
  stage_stock_id: number | null
  available_quantity: number
  processing_quantity: number
  pending_qc_quantity: number
  completed_quantity: number
  open_work_orders: SubstepOpenWorkOrder[]
  can_create_work_order: boolean
  can_submit_qc: boolean
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
  source_substep_id: number | null
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
  procedure_stage_stock_id: number | null
  production_item_id: number
  flow_node_id: string
  source_flow_node_id: string | null
  substep_id: number | null
  work_order_type: 'substep' | 'assembly'
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
  substepId: number
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
