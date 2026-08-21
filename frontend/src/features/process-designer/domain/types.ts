export const PROCESS_FLOW_SCHEMA_VERSION = 4 as const

export type FlowNodeType = 'part' | 'process' | 'qc' | 'assembly' | 'shipping'

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
  workshop_id: number
}

export type QcFlowNode = FlowNodeBase & { type: 'qc' }
export type ShippingFlowNode = FlowNodeBase & { type: 'shipping' }

export type AssemblyFlowNode = FlowNodeBase & {
  type: 'assembly'
  workshop_id: number
  output_name: string
  output_pcs: number
  assembly_sequence?: number
  assembly_code?: string
  assembly_name?: string
}

export type FlowNode = PartFlowNode | ProcessFlowNode | QcFlowNode | ShippingFlowNode | AssemblyFlowNode

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
  order_ready: boolean
  order_ready_reason: string
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
  order_ready: boolean
  order_ready_reason: string
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

export function synchronizeFlowPartMetadata(
  flow: ProcessFlow,
  bomItems: BomItem[],
  factoryCode = '',
): ProcessFlow {
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
  return synchronizeAssemblyIdentity(synchronized, factoryCode)
}

export function synchronizeAssemblyIdentity(flow: ProcessFlow, factoryCode = ''): ProcessFlow {
  const nodes = flow.nodes.map(node => ({ ...node }))
  const byId = new Map(nodes.map(node => [node.id, node]))
  const incoming = new Map<string, string[]>()
  flow.edges.forEach((edge) => {
    incoming.set(edge.target_node_id, [...(incoming.get(edge.target_node_id) || []), edge.source_node_id])
  })
  incoming.forEach(sourceIds => sourceIds.sort((left, right) => {
    const a = byId.get(left)
    const b = byId.get(right)
    return (a?.x ?? 0) - (b?.x ?? 0)
      || (a?.y ?? 0) - (b?.y ?? 0)
      || left.localeCompare(right)
  }))
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
    if (node.type === 'assembly' && result.length) {
      node.assembly_name = `${result.join('-')}装配体`
      node.output_name = node.assembly_name
    }
    return result
  }
  nodes.forEach(node => names(node.id))
  nodes
    .filter((node): node is AssemblyFlowNode => node.type === 'assembly')
    .sort((a, b) => a.x - b.x || a.y - b.y || a.id.localeCompare(b.id))
    .forEach((node, index) => {
      node.assembly_sequence = 81 + index
      node.assembly_code = factoryCode ? `${factoryCode}-${node.assembly_sequence}` : undefined
      node.assembly_name ||= node.output_name || '装配体'
      node.output_name = node.assembly_name
    })
  return { ...flow, nodes }
}
