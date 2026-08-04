export const PROCESS_FLOW_SCHEMA_VERSION = 3 as const
export type FlowNodeType = 'part' | 'process' | 'qc' | 'assembly' | 'shipping'
export type FlowPoint = { x: number; y: number }
type FlowNodeBase = FlowPoint & { id: string; label: string; label_position?: FlowPoint; z_index?: number; rotation?: number }
export type FlowNode =
  | (FlowNodeBase & { type: 'part'; bom_item_id: number; part_no: string })
  | (FlowNodeBase & {
      type: 'process'
      process_code: string
      procedure_id: number
    })
  | (FlowNodeBase & { type: 'qc' })
  | (FlowNodeBase & { type: 'shipping' })
  | (FlowNodeBase & {
      type: 'assembly'
      output_name: string
      output_pcs: number
      assembly_sequence?: number
      assembly_code?: string
      assembly_name?: string
    })
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
