import type LogicFlow from '@logicflow/core'
import { readDisplayPreference } from '@/shared/storage/displayPreferences'

export const PROCESS_FLOW_FONT_SIZE_STORAGE_KEY = 'zzerp.processFlow.fontSize'
export const PROCESS_FLOW_NODE_SCALE_STORAGE_KEY = 'zzerp.processFlow.nodeScale'
export const PROCESS_FLOW_MIN_CANVAS_SCALE = 0.02

export function storedProcessFlowNumber(
  key: string,
  fallback: number,
  minimum: number,
  maximum = Number.POSITIVE_INFINITY,
) {
  const stored = readDisplayPreference(key)
  if (stored === null || stored.trim() === '') return fallback
  const value = Number(stored)
  return Number.isFinite(value)
    ? Math.min(maximum, Math.max(minimum, value))
    : fallback
}

export function applyProcessNodeScale(
  lf: LogicFlow,
  scale: number,
  nodeId?: string,
) {
  const nodeIds = nodeId ? [nodeId] : lf.graphModel.nodes.map(node => node.id)
  nodeIds.forEach((id) => {
    const model = lf.getNodeModelById(id)
    if (model?.properties.__displayScale !== scale) {
      lf.setProperties(id, { __displayScale: scale })
    }
  })
  refreshProcessEdgeEndpoints(lf)
}

function refreshProcessEdgeEndpoints(lf: LogicFlow) {
  lf.graphModel.edges.forEach((edge) => {
    const startPoint = edge.getBeginAnchor(
      edge.sourceNode,
      edge.targetNode,
      edge.sourceAnchorId,
    )
    const endPoint = edge.getEndAnchor(edge.targetNode, edge.targetAnchorId)
    if (!startPoint || !endPoint) return
    const pointsList = edge.pointsList.length
      ? edge.pointsList.map((point, index, points) => (
          index === 0
            ? { x: startPoint.x, y: startPoint.y }
            : index === points.length - 1
              ? { x: endPoint.x, y: endPoint.y }
              : point
        ))
      : []
    edge.updateAttributes({
      startPoint: { x: startPoint.x, y: startPoint.y },
      endPoint: { x: endPoint.x, y: endPoint.y },
      pointsList,
    })
    edge.initPoints()
  })
}
