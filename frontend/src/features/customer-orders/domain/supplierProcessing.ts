export type SupplierProcessingTask = {
  production_plan_id: number
  production_plan_item_id: number
  production_item_id: number
  customer_order_item_id: number
  product_id: number
  product_version: number
  product_bom_id: number
  source_flow_node_id: string
  supplier_flow_node_id: string
  department_id: number
  item_code: string
  item_name: string
  task_quantity: number
  plan_status: string
  work_order_id: number | null
  work_order_status: 'open' | 'closed' | 'cancelled' | null
  can_create_work_order: boolean
}

export type SupplierProcessingWorkOrderInput = {
  production_plan_item_id: number
  supplier_flow_node_id: string
  supplier_name: string
  supplier_process_name: string
  remark: string | null
}
