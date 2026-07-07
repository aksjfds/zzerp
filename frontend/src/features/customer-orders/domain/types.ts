import type { ProcessFlow } from '@/features/process-designer/domain/types'

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
  customer_name: string
  status: CustomerOrderStatus
  revision: number
  remark: string
  items: CustomerOrderItem[]
  created_at: string
  updated_at: string
}

export type CustomerOrderPayload = {
  customer_order_no: string
  customer_name: string
  remark: string
  items: Array<Pick<CustomerOrderItem, 'product_id' | 'quantity' | 'delivery_date' | 'remark'>>
  expected_revision?: number
}

export type ProductionNodeStat = {
  flow_node_id: string
  node_type: string
  current_quantity: number
  entered_quantity: number
  transferred_quantity: number
  abnormal_quantity: number
  output_quantity: number
  input_details: Record<string, number>
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
  }>
}
