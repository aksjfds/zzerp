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
