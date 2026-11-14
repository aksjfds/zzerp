export type PlanStatus = 'draft' | 'confirmed' | 'cancelled' | 'completed'
export type PlanAction = 'confirm' | 'unconfirm' | 'complete' | 'reopen' | 'cancel'

export type ProductionPlanItemInput = {
  order_quantity: number
  product_id: number
  appearance_id: number
  production_quantity: number
}

export type ProductionPlanInput = {
  customer_id: number
  order_no: string
  items: ProductionPlanItemInput[]
}

export type ProductionPlan = Omit<ProductionPlanInput, 'items'> & {
  items: (ProductionPlanItemInput & { product_name: string; factory_code: string; appearance_name: string })[]
  id: number
  customer_name: string
  status: PlanStatus
  revision: number
  confirmed_at: string | null
  confirmed_by: string | null
  completed_at: string | null
  completed_by: string | null
  created_at: string
  updated_at: string
}

export type PlanProduct = {
  appearance_id: number
  appearance_name: string
  id: number
  customer_id: number
  product_name: string
  factory_code: string
}

export type WorkOrderComponent = {
  material_node_id: string
  part_no: string
  part_name: string
  required_quantity: string
  received_quantity: string
}

export type DepartmentWorkOrder = {
  appearance_name: string
  id: number
  production_plan_id: number
  material_node_id: string
  department_node_id: string
  order_no: string
  order_quantity: number
  customer_name: string
  product_id: number
  factory_code: string
  product_name: string
  part_no: string
  part_name: string
  department_code: string
  department_name: string
  can_receive: boolean
  task_quantity: number
  received_quantity: string
  issued_quantity: string
  plan_status: ProductionPlan['status']
  components: WorkOrderComponent[]
}

export type ProgressProduct = {
  appearance_id: number
  appearance_name: string
  product_id: number
  factory_code: string
  product_name: string
  materials: {
    material_node_id: string
    part_no: string
    part_name: string
    work_orders: DepartmentWorkOrder[]
  }[]
}

export type ProgressPlan = {
  production_plan_id: number
  order_no: string
  customer_name: string
  products: ProgressProduct[]
}

export type DepartmentMovementInput = {
  direction: 'receipt' | 'issue'
  quantity: number
  note: string
  request_id: string
  receipt_source: 'external' | 'ticket' | null
  ticket_id: number | null
  input_material_node_id: string | null
  target_work_order_id: number | null
}

export type DepartmentMovement = DepartmentMovementInput & {
  source_department: string | null
  target_department: string | null
  id: number
  actor_username: string
  created_at: string
  ticket_no: string | null
  material_name: string
}

export type DepartmentLedgerMovement = DepartmentMovement & {
  appearance_id: number; appearance_name: string
  order_no: string; factory_code: string; product_name: string; department_name: string
}

export type HandoffOptions = {
  available_issue_quantity: string | null
  can_receive: boolean
  targets: { id: number; label: string }[]
  external_inputs: { material_node_id: string; label: string }[]
}

export type HandoffTicket = {
  appearance_id: number; appearance_name: string
  can_receive: boolean
  id: number; ticket_no: string; order_no: string; material_name: string
  factory_code: string; product_name: string
  source_department: string; target_department: string; quantity: number; received_quantity: string
  created_at: string; note: string; target_work_order_id: number; plan_status: ProductionPlan['status']
}
