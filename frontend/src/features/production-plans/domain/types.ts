import type { BomItem, ProcessFlow } from '@/features/process-designer'

export type PlanStatus = 'draft' | 'confirmed' | 'cancelled' | 'completed'
export type PlanAction = 'confirm' | 'unconfirm' | 'complete' | 'reopen' | 'cancel'

export type ProductionPlanItemInput = {
  source_version?: number
  order_quantity: number
  product_id: number
  production_quantity: number
}

export type ProductionPlanInput = {
  customer_id: number
  order_no: string
  order_date: string
  delivery_date: string
  items: ProductionPlanItemInput[]
}

export type ProductionPlan = Omit<ProductionPlanInput, 'items'> & {
  items: (ProductionPlanItemInput & { product_name: string; factory_code: string; source_version: number; source_version_value: string; customer_code: string })[]
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


export type PlanProductSnapshot = {
  product_id: number
  source_version: number
  source_version_value: string
  product_name: string
  factory_code: string
  customer_code: string
  bom_items: BomItem[]
  process_flow: ProcessFlow
}
