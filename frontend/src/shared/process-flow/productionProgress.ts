import type { FlowNodeType } from './types'

export type ProductionNodeStat = {
  flow_node_id: string
  node_type: FlowNodeType
  current_quantity: number
  entered_quantity: number
  transferred_quantity: number
  abnormal_quantity: number
  output_quantity: number
  pending_receipt_quantity: number
  received_quantity: number
  input_details: Record<string, number>
}

export type ProductionEdgeStat = {
  flow_edge_id: string
  transferred_quantity: number
}
