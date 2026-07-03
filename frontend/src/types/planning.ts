import type { MaterialType } from './engineering'

export type ProductionPlanStatus =
  | 'draft'
  | 'released'
  | 'producing'
  | 'completed'
  | 'cancelled'

export type PlanMaterial = {
  id?: number | null
  customerOrderItemId: number
  materialId: number
  materialCode: string
  materialName: string
  materialType: MaterialType
  theoreticalQuantity: number
  plannedQuantity: number
  adjustmentReason?: string | null
  semiFinishedVersionId?: number | null
  routeVersionId?: number | null
}

export type PlanOrderItem = {
  id?: number | null
  customerOrderItemId: number
  factoryCode: string
  productName: string
  customerProductCode: string
  treatmentName?: string | null
  orderRequiredQuantity: number
  plannedFinishedQuantity: number
  stockQuantity: number
  productBomVersionId: number
  materials: PlanMaterial[]
}

export type ProductionPlanPreview = {
  customerOrderId: number
  items: PlanOrderItem[]
}

export type ProductionPlan = ProductionPlanPreview & {
  id: number
  planNo: string
  customerName: string
  purchaseOrderNo: string
  status: ProductionPlanStatus
  startDate: string
  completionDate: string
}

export type PlanItemInput = {
  customerOrderItemId: number
  plannedFinishedQuantity: number
}

export type PlanMaterialAdjustmentInput = {
  customerOrderItemId: number
  materialId: number
  plannedQuantity: number
  adjustmentReason?: string
}
