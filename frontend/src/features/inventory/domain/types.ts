import type { CustomerOrderStatus } from '@/features/customer-orders'

export type FinishedOrderStatus = Extract<CustomerOrderStatus, 'planned' | 'closed'>

export type FinishedReceipt = {
  id: number
  work_order_batch_id: number | null
  work_order_id: number | null
  product_id: number
  product_version: number
  item_code: string
  item_name: string
  quantity: number
  status: 'pending' | 'received' | 'cancelled' | 'reversed'
  received_at: string | null
  received_by: string | null
  corrected_at: string | null
  corrected_by: string | null
  correction_reason: string | null
  created_at: string
  revision: number
}

export type PendingFinishedReceipt = {
  id: number
  work_order_batch_id: number | null
  work_order_id: number | null
  quantity: number
  created_at: string
}

export type FinishedInboundItem = {
  product_id: number
  product_version: number
  item_code: string
  item_name: string
  planned_quantity: number
  production_plan_count: number
  arrived_quantity: number
  pending_receipts: PendingFinishedReceipt[]
  updated_at: string
}

export type FinishedStock = {
  id: number
  product_id: number
  item_code: string
  item_name: string
  product_version: number
  quantity: number
  reserved_quantity: number
  available_quantity: number
  revision: number
  updated_at: string
}

export type FinishedStockTransaction = {
  id: number
  finished_stock_id: number
  finished_receipt_id: number | null
  finished_stock_reservation_id: number | null
  operation_group_no: string
  reversal_of_transaction_id: number | null
  customer_order_id: number | null
  customer_order_no: string
  customer_order_item_id: number | null
  product_id: number
  product_version: number
  item_code: string
  item_name: string
  transaction_type: 'receipt' | 'receipt_reversal' | 'customer_shipment' | 'customer_shipment_reversal'
  quantity: number
  quantity_before: number
  quantity_after: number
  actor_username: string
  reason: string
  created_at: string
}

export type FinishedShipmentCandidate = {
  customer_order_id: number
  customer_order_no: string
  order_status: FinishedOrderStatus
  customer_order_item_id: number
  item_code: string
  item_name: string
  product_version: number
  required_quantity: number
  reserved_quantity: number
  unreserved_quantity: number
  available_quantity: number
  shipped_quantity: number
  outstanding_quantity: number
}

export type WarehouseItemType = 'part' | 'assembly'
export type WarehouseOperationType = 'inbound' | 'outbound'
export type WarehouseOperationStatus = 'pending' | 'succeeded' | 'failed' | 'uncertain'
export type WarehouseOperationSource = 'plan_confirmation' | 'qc_inventory' | 'production_position' | 'reversal'

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
  processing_state_id: number
  reversal_of_operation_id: number | null
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
