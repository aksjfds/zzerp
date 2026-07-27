export type PmcProgressDepartment = {
  department_id: number
  department_code: string
  department_name: string
}

export type PmcPartDepartmentProgress = {
  in_route: boolean
  waiting_quantity: number
  processing_quantity: number
  pending_qc_quantity: number
  completed_quantity: number
  scrap_quantity: number
  lost_quantity: number
}

export type PmcPartProgressRow = {
  production_item_id: number
  customer_order_id: number
  customer_order_no: string
  customer_name: string
  order_status: string
  factory_code: string
  product_name: string
  part_name: string
  part_display_name: string
  target_quantity: number
  delivery_date: string
  departments: Record<string, PmcPartDepartmentProgress>
}

export type PmcPartProgressResult = {
  data: PmcPartProgressRow[]
  total: number
  departments: PmcProgressDepartment[]
}
