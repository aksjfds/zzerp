export type CustomerOrderStatus =
  | 'draft'
  | 'confirmed'
  | 'planned'
  | 'completed'
  | 'cancelled'
  | 'superseded'

export type CustomerOrderItem = {
  id: number
  productId: number
  factoryCode: string
  productName: string
  productCustomerCodeId: number
  customerProductCode: string
  treatmentId?: number | null
  treatmentName?: string | null
  quantity: number
  deliveryDate: string
}

export type CustomerOrder = {
  id: number
  customerName: string
  purchaseOrderNo: string
  versionNo: number
  previousVersionId?: number | null
  status: CustomerOrderStatus
  orderDate: string
  note?: string | null
  items: CustomerOrderItem[]
}

export type CustomerOrderItemInput = {
  productCustomerCodeId: number
  treatmentId?: number
  quantity: number
  deliveryDate: string
}

export type CustomerOrderCreateInput = {
  customerName: string
  purchaseOrderNo: string
  orderDate: string
  note?: string
  items: CustomerOrderItemInput[]
}

export type CustomerOrderUpdateInput = Omit<
  CustomerOrderCreateInput,
  'customerName' | 'purchaseOrderNo'
>
