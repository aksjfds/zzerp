import type { ProcessFlow } from '@/shared/process-flow/types'
import type {
  ProductionEdgeStat,
  ProductionNodeStat,
} from '@/shared/process-flow/productionProgress'

export type CustomerOrderStatus = 'draft' | 'confirmed' | 'planned' | 'cancelled' | 'closed'
export type ProductionPlanStatus = 'draft' | 'confirmed' | 'cancelled' | 'completed'

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
  production_plan_status: ProductionPlan['status'] | null
  can_edit: boolean
  revision: number
  remark: string
  items: CustomerOrderItem[]
  created_at: string
  updated_at: string
}

export type CustomerOrderProgressDetail = {
  customer_order_id: number
  customer_order_item_id: number
  factory_code: string
  product_name: string
  order_date: string
  customer_order_no: string
  customer_code: string
  order_quantity: number
  task_quantity: number
  shipped_quantity: number
  outstanding_quantity: number
  delivery_date: string
  remark: string
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
  net_required_quantity: number
  planned_production_quantity: number
  allocated_inventory_quantity: number
}

export type ProductionPlan = {
  id: number
  customer_order_id: number
  status: ProductionPlanStatus
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
    warehouse_code: string
    warehouse_name: string
    stock_quantity: number
    reserved_quantity: number
    available_quantity: number
    planned_allocation_quantity: number
    allocation_mode: 'reservation' | 'outbound'
    decomposition: {
      finished_equivalent_quantity: number
      parts: Array<{
        product_bom_id: number
        item_code: string
        item_name: string
        quantity: number
      }>
    }
  }>
  confirmed_at: string | null
  confirmed_by: string | null
  completed_at: string | null
  completed_by: string | null
  created_at: string
  updated_at: string
}

export type { ProductionEdgeStat, ProductionNodeStat }
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
