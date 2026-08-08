import type { FlowNodeType, ProcessFlow } from '@/shared/process-flow/types'

export type CustomerOrderStatus = 'draft' | 'confirmed' | 'planned' | 'cancelled' | 'closed'

export type CustomerOrderItem = {
  id?: number
  product_id: number
  product_version?: number
  product_name?: string
  factory_code?: string
  quantity: number
  delivery_date: string
  remark: string
}

export type CustomerOrder = {
  id: number
  customer_order_no: string
  customer_id: number
  customer_name: string
  status: CustomerOrderStatus
  revision: number
  remark: string
  items: CustomerOrderItem[]
  product_progress: CustomerOrderProductProgress[]
  created_at: string
  updated_at: string
}

export type CustomerOrderProductProgress = {
  customer_order_item_id: number
  product_id: number
  product_name: string
  factory_code: string
  total_quantity: number
  completed_quantity: number
  scrap_quantity: number
  lost_quantity: number
  unfinished_quantity: number
  po_shortage_quantity: number
}

export type CustomerOrderPayload = {
  customer_order_no: string
  customer_id: number
  remark: string
  items: Array<Pick<CustomerOrderItem, 'id' | 'product_id' | 'quantity' | 'delivery_date' | 'remark'>>
  expected_revision?: number
}

export type ProductionPlanItem = {
  id: number
  customer_order_item_id: number
  item_type: 'finished_product' | 'assembly' | 'part'
  product_id: number
  product_version: number
  product_bom_id: number | null
  flow_node_id: string
  item_code: string
  item_name: string
  unit_requirement: number
  gross_required_quantity: number
  estimated_inventory_quantity: number
  available_inventory_quantity: number
  net_required_quantity: number
  planned_production_quantity: number
  reserved_inventory_quantity: number
  issued_inventory_quantity: number
}

export type ProductionPlan = {
  id: number
  customer_order_id: number
  status: 'draft' | 'confirmed' | 'cancelled'
  revision: number
  product_summaries: Array<{
    customer_order_item_id: number
    product_id: number
    product_version: number
    product_code: string
    product_name: string
    order_quantity: number
    planned_finished_quantity: number
  }>
  items: ProductionPlanItem[]
  inventory_items: Array<{
    id: number
    customer_order_item_id: number
    item_type: 'finished_product' | 'assembly' | 'part'
    product_id: number
    product_version: number
    product_bom_id: number | null
    flow_node_id: string
    item_code: string
    item_name: string
    completed_node_label: string
    current_inventory_quantity: number
    reserved_inventory_quantity: number
    issued_inventory_quantity: number
  }>
  confirmed_at: string | null
  confirmed_by: string | null
  created_at: string
  updated_at: string
}

export type ProductionNodeStat = {
  flow_node_id: string
  node_type: FlowNodeType
  current_quantity: number
  entered_quantity: number
  transferred_quantity: number
  abnormal_quantity: number
  output_quantity: number
  input_details: Record<string, number>
}
export type ProductionEdgeStat = {
  flow_edge_id: string
  transferred_quantity: number
}
export type CustomerOrderProduction = {
  customer_order_id: number
  status: CustomerOrderStatus
  products: Array<{
    customer_order_item_id: number
    product_name: string
    factory_code: string
    product_version: number
    order_quantity: number
    process_flow: ProcessFlow
    node_stats: ProductionNodeStat[]
    edge_stats: ProductionEdgeStat[]
  }>
}
