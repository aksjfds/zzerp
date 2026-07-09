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
  procedure_id: number
}

export type AssemblyFlowNode = FlowNodeBase & {
  type: 'assembly'
  output_name: string
  output_pcs: number
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
  product_version?: number
  part_name: string
  part_no: string
  pcs: number
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
  revision: number
  bom_count: number
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
  bom_items: BomItem[]
  process_flow: ProcessFlow
  created_at: string
  updated_at: string
}

export type CreateProductPayload = ProductFields & { bom_items: BomItem[] }

export type ProductForm = ProductFields & {
  version: number | null
  revision: number | null
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
  const synchronized = {
    ...flow,
    nodes: flow.nodes.map((node) => {
      if (node.type !== 'part') return node
      const item = metadata.get(node.bom_item_id)
      return item ? { ...node, label: item.part_name, part_no: item.part_no } : node
    }),
  }
  return synchronizeAssemblyNames(synchronized)
}

export function synchronizeAssemblyNames(flow: ProcessFlow): ProcessFlow {
  const nodes = flow.nodes.map(node => ({ ...node }))
  const byId = new Map(nodes.map(node => [node.id, node]))
  const incoming = new Map<string, string[]>()
  flow.edges.filter(edge => edge.route_type === 'normal').forEach((edge) => {
    incoming.set(edge.target_node_id, [...(incoming.get(edge.target_node_id) || []), edge.source_node_id])
  })
  const cache = new Map<string, string[]>()
  function names(nodeId: string, visiting = new Set<string>()): string[] {
    if (cache.has(nodeId)) return cache.get(nodeId)!
    if (visiting.has(nodeId)) return []
    const node = byId.get(nodeId)
    if (!node) return []
    if (node.type === 'part') return [node.label]
    const result: string[] = []
    const nextVisiting = new Set(visiting).add(nodeId)
    for (const sourceId of incoming.get(nodeId) || []) {
      for (const name of names(sourceId, nextVisiting)) if (!result.includes(name)) result.push(name)
    }
    cache.set(nodeId, result)
    if (node.type === 'assembly' && result.length) node.output_name = `${result.join('-')}装配体`
    return result
  }
  nodes.forEach(node => names(node.id))
  return { ...flow, nodes }
}
