import type { CustomerOrderStatus } from '@/features/customer-orders'

export type FinishedInventoryTransactionSource = 'finished_inventory_stock' | 'finished_order_stock'
export type FinishedOrderStatus = Extract<CustomerOrderStatus, 'planned' | 'closed'>

export type FinishedInventoryStock = {
  id: number
  product_id: number
  item_code: string
  item_name: string
  product_version: number
  flow_node_id: string
  completed_flow_node_id: string
  completed_node_label: string
  quantity: number
  available_quantity: number
  revision: number
}

export type FinishedInventoryTransaction = {
  id: number
  source_type: FinishedInventoryTransactionSource
  source_id: number
  finished_inventory_stock_id: number | null
  production_plan_id: number | null
  transaction_type: string
  quantity: number
  quantity_before: number
  quantity_after: number
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

export type WarehouseItemType = 'part' | 'assembly'
export type WarehouseOperationType = 'inbound' | 'outbound'
export type WarehouseOperationStatus = 'pending' | 'succeeded' | 'failed' | 'uncertain'
export type WarehouseOperationSource = 'plan_confirmation' | 'qc_inventory' | 'production_position'

export type WarehouseStock = {
  id: number
  item_code: string
  item_name: string
  product_version: number
  item_type: WarehouseItemType
  specification: string
  inventory_unit: 'PCS'
  warehouse_code: 'C01' | 'C02'
  warehouse_name: '主料仓' | '辅料仓'
  quantity: number
  completion_status: string
  last_inbound_date: string | null
  last_outbound_date: string | null
}

export type WarehouseOperation = {
  id: number
  operation_group_no: string
  operation_no: string
  operation_type: WarehouseOperationType
  source_type: WarehouseOperationSource
  production_plan_id: number | null
  production_plan_item_id: number | null
  work_order_id: number | null
  work_order_batch_id: number | null
  production_item_id: number | null
  warehouse_stock_id: number | null
  item_code: string
  item_name: string
  product_version: number
  item_type: WarehouseItemType
  specification: string
  inventory_unit: 'PCS'
  warehouse_code: 'C01' | 'C02'
  warehouse_name: '主料仓' | '辅料仓'
  completion_status: string
  quantity: number
  quantity_before: number | null
  quantity_after: number | null
  status: WarehouseOperationStatus
  actor_username: string
  error_message: string | null
  created_at: string
  executed_at: string | null
  manual_reviewed_at: string | null
  manual_reviewed_by: string | null
  manual_review_note: string | null
  can_review: boolean
}
