export type InventoryDepartment = 'warehouse' | 'finished'

export type InventoryStock = {
  id: number
  department_code: InventoryDepartment
  item_type: 'part' | 'assembly' | 'finished_product'
  item_code: string
  item_name: string
  product_version: number
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
}

export type FinishedOrderStock = {
  customer_order_id: number
  customer_order_no: string
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
