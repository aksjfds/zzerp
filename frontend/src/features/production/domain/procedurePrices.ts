export type ProcedurePriceItem = {
  procedure_id: number
  procedure_name: string
  unit_price: number | string | null
  referenced: boolean
}

export type ProcedurePriceScope = {
  product_id: number
  product_version: number
  product_name: string
  factory_code: string
  product_bom_id: number | null
  origin_flow_node_id: string
  flow_node_id: string
  workshop_id: number
  workshop_name: string
  part_name: string
  part_no: string
  procedures: ProcedurePriceItem[]
}
