export type ProcedurePriceItem = {
  procedure_id: number
  procedure_name: string
  unit_price: number | string | null
  referenced: boolean
}

export type ProcedurePriceScope = {
  row_type: 'formal'
  product_id: number
  product_version: number
  origin_flow_node_id: string
  flow_node_id: string
  product_name: string
  factory_code: string
  product_bom_id: number | null
  workshop_id: number
  workshop_name: string
  part_name: string
  part_no: string
  confirmed: boolean
  can_cancel: boolean
  confirmed_at: string | null
  confirmed_by: string | null
  procedures: ProcedurePriceItem[]
}

export type TemporaryWorkOrderPriceItem = {
  row_type: 'temporary'
  work_order_id: number
  work_order_no: string
  product_id: number
  product_version: number
  origin_flow_node_id: string
  flow_node_id: string
  product_name: string
  factory_code: string
  part_name: string
  part_no: string
  workshop_name: string
  procedure_name: string
  unit_price: number | string | null
  status: 'open' | 'closed' | 'cancelled'
  created_at: string
}

export type ProcedurePriceListItem = ProcedurePriceScope | TemporaryWorkOrderPriceItem

export type ProcedurePriceRevision = {
  id: number
  target_type: 'formal' | 'temporary'
  target_label: string
  previous_unit_price: number | string | null
  new_unit_price: number | string | null
  actor_username: string
  created_at: string
}
