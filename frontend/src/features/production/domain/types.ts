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
  source_flow_node_id: string
  source_node_label: string
  procedure_name: string
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
  flow_node_id: string
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
  production_item_id: number
  input_production_item_ids: number[]
  customer_order_no: string
  part_no: string
  part_name: string
  procedure_name: string
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
  procedure_name: string
  remaining_quantity: number
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
