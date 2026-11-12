import { PROCESS_FLOW_SCHEMA_VERSION, type ProcessFlow } from '@/shared/process-flow/types'
export { PROCESS_FLOW_SCHEMA_VERSION } from '@/shared/process-flow/types'
export type { FlowNodeType, FlowPoint, FlowNode, FlowEdge, ProcessFlow } from '@/shared/process-flow/types'

export type BomItem = {
  id?: number
  product_version?: number
  part_name: string
  part_no: string
  pcs: number
  remark: string
  sort_order?: number
}

export type ProductFields = {
  customer_id: number | null
  customer_name: string
  product_name: string
  factory_code: string
  customer_code: string
}

export type ProductSummary = ProductFields & {
  id: number
  version: number
  revision: number
  bom_count: number
  design_ready: boolean
  design_ready_reason: string
  created_at: string
  updated_at: string
}

export type EngineeringProduct = ProductFields & {
  id: number
  version: number
  current_version: number
  revision: number
  base_info_editable: boolean
  version_editable: boolean
  design_ready: boolean
  design_ready_reason: string
  bom_items: BomItem[]
  process_flow: ProcessFlow
  process_flow_is_draft: boolean
  created_at: string
  updated_at: string
}

export type CreateProductPayload = ProductFields & { bom_items: BomItem[] }

export type ProductForm = ProductFields & {
  version: number | null
  revision: number | null
  bom_items: BomItem[]
  process_flow: ProcessFlow
  process_flow_is_draft: boolean
}

export const EMPTY_FLOW = (): ProcessFlow => ({
  schema_version: PROCESS_FLOW_SCHEMA_VERSION,
  nodes: [],
  edges: [],
})
