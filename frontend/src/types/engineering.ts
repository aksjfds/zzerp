export type MasterDataStatus = 'draft' | 'published' | 'inactive'
export type MaterialType = 'finished' | 'semi_finished' | 'self_made' | 'purchased'

export type DepartmentSummary = {
  id: number
  departmentCode: string
  departmentName: string
  departmentType: 'system' | 'office' | 'production' | 'quality'
  active: boolean
}

export type WorkshopSummary = {
  id: number
  departmentId: number
  workshopCode: string
  workshopName: string
  active: boolean
}

export type SurfaceTreatmentSummary = {
  id: number
  customerName: string
  treatmentName: string
  active: boolean
}

export type ProductCustomerCodeDetail = {
  id: number
  productId: number
  customerName: string
  customerProductCode: string
  active: boolean
  treatmentIds: number[]
}

export type MaterialSummary = {
  id: number
  productId: number
  materialCode: string
  materialName: string
  materialType: MaterialType
  materialGrade?: string | null
  specification?: string | null
  note?: string | null
  active: boolean
}

export type EngineeringProduct = {
  id: number
  factoryCode: string
  productName: string
  status: MasterDataStatus
  publishedBy?: number | null
  publishedAt?: string | null
  customerCodes: ProductCustomerCodeDetail[]
  materials: MaterialSummary[]
}

export type ProductCustomerCodeInput = {
  customerName: string
  customerProductCode: string
  treatmentIds: number[]
}

export type MaterialInput = {
  materialCode?: string
  materialName: string
  materialType: Exclude<MaterialType, 'finished'>
  materialGrade?: string
  specification?: string
  note?: string
}

export type ProductInput = {
  factoryCode: string
  productName: string
  customerCodes: ProductCustomerCodeInput[]
  materials: MaterialInput[]
}

export type BomItem = {
  id: number
  materialId: number
  materialCode: string
  materialName: string
  materialType: MaterialType
  quantity: number
  unit: 'pcs'
}

export type ProductBomVersion = {
  id: number
  productId: number
  versionNo: number
  status: MasterDataStatus
  items: BomItem[]
}

export type SemiFinishedInput = Omit<BomItem, 'materialId'> & {
  inputMaterialId: number
}

export type SemiFinishedVersion = {
  id: number
  semiFinishedMaterialId: number
  materialCode: string
  materialName: string
  versionNo: number
  quantityPerFinished: number
  status: MasterDataStatus
  inputs: SemiFinishedInput[]
}

export type ProductionStructureNode = {
  id: string
  materialId: number
  materialCode: string
  materialName: string
  materialType: MaterialType
  quantity: number
  children: ProductionStructureNode[]
}

export type ProductionStructure = {
  productId: number
  bomVersionId: number
  root: ProductionStructureNode
}

export type RouteStepType = 'internal' | 'external_surface'

export type MaterialRouteStep = {
  id: number
  sequenceNo: number
  stepType: RouteStepType
  departmentId?: number | null
  workshopId?: number | null
  departmentName?: string | null
  workshopName?: string | null
}

export type MaterialRouteVersion = {
  id: number
  materialId: number
  materialCode: string
  materialName: string
  versionNo: number
  status: MasterDataStatus
  steps: MaterialRouteStep[]
}
