export const PROCESS_FLOW_SCHEMA_VERSION = 1 as const

export type FlowNodeType = 'part' | 'process' | 'assembly' | 'qc'
export type RouteType = 'normal' | 'rework'
export type FlowOutcome = 'approved' | 'rejected'

export type FlowPoint = { x: number; y: number }

type FlowNodeBase = FlowPoint & {
  id: string
  label: string
  label_position?: FlowPoint
  z_index?: number
  rotation?: number
}

export type PartFlowNode = FlowNodeBase & {
  type: 'part'
  bom_item_id: number
  part_no: string
}

export type ProcessFlowNode = FlowNodeBase & {
  type: 'process'
  process_code: string
}

export type AssemblyFlowNode = FlowNodeBase & {
  type: 'assembly'
  output_name: string
}

export type QcFlowNode = FlowNodeBase & { type: 'qc' }
export type FlowNode = PartFlowNode | ProcessFlowNode | AssemblyFlowNode | QcFlowNode

export type FlowEdge = {
  id: string
  edge_type: string
  source_node_id: string
  target_node_id: string
  source_anchor_id?: string
  target_anchor_id?: string
  start_point?: FlowPoint
  end_point?: FlowPoint
  points?: FlowPoint[]
  label?: string
  label_position?: FlowPoint
  z_index?: number
  route_type: RouteType
  outcome?: FlowOutcome
}

export type ProcessFlow = {
  schema_version: typeof PROCESS_FLOW_SCHEMA_VERSION
  nodes: FlowNode[]
  edges: FlowEdge[]
}

export type BomItem = {
  id?: number
  part_name: string
  part_no: string
  pcs: string
  remark: string
  sort_order?: number
}

export type ProductFields = {
  customer_name: string
  product_name: string
  factory_code: string
  customer_code: string
}

export type ProductSummary = ProductFields & {
  id: number
  version: number
  bom_count: number
  created_at: string
  updated_at: string
}

export type EngineeringProduct = ProductFields & {
  id: number
  version: number
  bom_items: BomItem[]
  process_flow: ProcessFlow
  created_at: string
  updated_at: string
}

export type CreateProductPayload = ProductFields & { bom_items: BomItem[] }

export type ProductForm = ProductFields & {
  version: number | null
  bom_items: BomItem[]
  process_flow: ProcessFlow
}

export const EMPTY_FLOW = (): ProcessFlow => ({
  schema_version: PROCESS_FLOW_SCHEMA_VERSION,
  nodes: [],
  edges: [],
})

export function synchronizeFlowPartMetadata(flow: ProcessFlow, bomItems: BomItem[]): ProcessFlow {
  const metadata = new Map(
    bomItems.flatMap((item) => item.id ? [[item.id, item] as const] : []),
  )
  return {
    ...flow,
    nodes: flow.nodes.map((node) => {
      if (node.type !== 'part') return node
      const item = metadata.get(node.bom_item_id)
      return item ? { ...node, label: item.part_name, part_no: item.part_no } : node
    }),
  }
}
