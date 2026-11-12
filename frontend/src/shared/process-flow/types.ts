export const PROCESS_FLOW_SCHEMA_VERSION = 8 as const
export type FlowNodeType = 'part' | 'department'
export type FlowPoint = { x: number; y: number }
type FlowNodeBase = FlowPoint & {
  id: string
  label: string
  label_position?: FlowPoint
  z_index?: number
  rotation?: number
}
export type FlowNode = FlowNodeBase & (
  | { type: 'part'; bom_item_id: number }
  | { type: 'department'; department_code: string }
)
export type FlowEdge = {
  id: string
  edge_type: 'polyline'
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
