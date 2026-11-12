import type LogicFlow from '@logicflow/core'
import { PROCESS_FLOW_GRID_X, PROCESS_FLOW_GRID_Y } from '@/shared/process-flow/adapter'

export function planAutoConnections(
  lf: LogicFlow,
  onError: (message: string) => void,
  addEdges: (edges: Array<{ sourceNodeId: string; targetNodeId: string }>) => void,
) {
  const selected = lf.getSelectElements().nodes
  if (selected.length < 2) return onError('请先框选至少两个节点')
  const xs = selected.map(node => node.x)
  const ys = selected.map(node => node.y)
  const horizontal = (Math.max(...xs) - Math.min(...xs)) / PROCESS_FLOW_GRID_X
    > (Math.max(...ys) - Math.min(...ys)) / PROCESS_FLOW_GRID_Y
  const nodes = [...selected].sort((a, b) => horizontal
    ? a.x - b.x || a.y - b.y || a.id.localeCompare(b.id)
    : a.y - b.y || a.x - b.x || a.id.localeCompare(b.id))
  const existing = new Set(lf.graphModel.edges.map(edge => JSON.stringify([edge.sourceNodeId, edge.targetNodeId])))
  const edges = nodes.slice(1).flatMap((target, index) => {
    const source = nodes[index]!
    return existing.has(JSON.stringify([source.id, target.id]))
      ? [] : [{ sourceNodeId: source.id, targetNodeId: target.id }]
  })
  if (edges.some(edge => nodes.find(node => node.id === edge.targetNodeId)?.type === 'part')) {
    return onError('配件节点不能作为连接目标，请调整节点位置或分开选择')
  }
  if (!edges.length) return onError('所选节点之间已存在连接')
  addEdges(edges)
}
