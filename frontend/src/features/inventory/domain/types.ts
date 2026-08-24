import type { CustomerOrderStatus } from '@/features/customer-orders'

export type InventoryDepartment = 'warehouse' | 'finished'
export type InventoryItemType = 'part' | 'assembly' | 'finished_product'
export type InventoryTransactionSource = 'inventory_stock' | 'finished_order_stock'
export type FinishedOrderStatus = Extract<CustomerOrderStatus, 'planned' | 'closed'>

export type InventoryStock = {
  id: number
  department_code: InventoryDepartment
  item_type: InventoryItemType
  item_code: string
  item_name: string
  product_version: number
  completed_flow_node_id: string
  completed_node_label: string
  quantity: number
  reserved_quantity: number
  available_quantity: number
}

export type InventoryOutboundItem = {
  reservation_id: number
  item_code: string
  item_name: string
  reserved_quantity: number
  issued_quantity: number
  remaining_quantity: number
  completed_node_label: string
  issue_quantity?: number
}

export type InventoryOutboundPlan = {
  production_plan_id: number
  customer_order_id: number
  customer_order_no: string
  department_code: InventoryDepartment
  items: InventoryOutboundItem[]
}

export type InventoryTransaction = {
  id: number
  source_type: InventoryTransactionSource
  source_id: number
  inventory_stock_id: number | null
  transaction_type: string
  quantity: number
  quantity_before: number
  quantity_after: number
  reserved_before: number
  reserved_after: number
  actor_username: string
  reason: string
  created_at: string
  item_code: string
  item_name: string
  customer_order_no: string
  completed_node_label: string
}

export type FinishedOrderStock = {
  customer_order_id: number
  customer_order_no: string
  order_status: FinishedOrderStatus
  customer_order_item_id: number
  item_code: string
  item_name: string
  product_version: number
  required_quantity: number
  pending_quantity: number
  available_quantity: number
  shipped_quantity: number
  outstanding_quantity: number
}
