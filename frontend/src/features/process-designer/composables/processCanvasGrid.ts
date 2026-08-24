import type LogicFlow from '@logicflow/core'

import { PROCESS_FLOW_GRID_X, PROCESS_FLOW_GRID_Y } from '@/shared/process-flow/adapter'
import { ProcessPolylineEdgeModel } from '@/shared/process-flow/registerNodes'

export function snapNodeToGrid(logicFlow: LogicFlow, nodeId: string) {
  const node = logicFlow.getNodeModelById(nodeId)
  if (!node) return
  const x = Math.round(node.x / PROCESS_FLOW_GRID_X) * PROCESS_FLOW_GRID_X
  const y = Math.round(node.y / PROCESS_FLOW_GRID_Y) * PROCESS_FLOW_GRID_Y
  if (x !== node.x || y !== node.y) {
    logicFlow.graphModel.moveNode2Coordinate(nodeId, x, y, true)
  }
}

export function snapSelectionToGrid(logicFlow: LogicFlow, anchorNodeId?: string) {
  const selectedNodes = logicFlow.getSelectElements().nodes
  const anchor = anchorNodeId
    ? selectedNodes.find(node => node.id === anchorNodeId)
    : selectedNodes[0]
  if (!anchor) {
    if (anchorNodeId) snapNodeToGrid(logicFlow, anchorNodeId)
    return
  }
  const deltaX = Math.round(anchor.x / PROCESS_FLOW_GRID_X) * PROCESS_FLOW_GRID_X - anchor.x
  const deltaY = Math.round(anchor.y / PROCESS_FLOW_GRID_Y) * PROCESS_FLOW_GRID_Y - anchor.y
  if (deltaX === 0 && deltaY === 0) return
  selectedNodes.forEach((node) => {
    logicFlow.graphModel.moveNode2Coordinate(node.id, node.x + deltaX, node.y + deltaY, true)
  })
}

export function replanConnectedEdges(logicFlow: LogicFlow, nodeIds: string[]) {
  const movedNodeIds = new Set(nodeIds)
  logicFlow.graphModel.edges.forEach((edge) => {
    if (!(edge instanceof ProcessPolylineEdgeModel)
      || (!movedNodeIds.has(edge.sourceNodeId) && !movedNodeIds.has(edge.targetNodeId))) return
    edge.updatePoints()
  })
}
