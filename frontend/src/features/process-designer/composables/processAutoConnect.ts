import type LogicFlow from '@logicflow/core'
import type { BaseNodeModel } from '@logicflow/core'

import { PROCESS_FLOW_GRID_X, PROCESS_FLOW_GRID_Y } from '@/shared/process-flow/adapter'

export function planAutoConnections(
  lf: LogicFlow,
  onConnectionError: (message: string) => void,
  addEdges: (edges: Array<{ sourceNodeId: string; targetNodeId: string }>) => void,
) {
  const selectedIds = new Set(lf.getSelectElements().nodes.map(node => node.id))
  const selectedNodes = lf.graphModel.nodes.filter(node => selectedIds.has(node.id))
  const xValues = selectedNodes.map(node => node.x)
  const yValues = selectedNodes.map(node => node.y)
  const horizontal = selectedNodes.length > 1
    && (Math.max(...xValues) - Math.min(...xValues)) / PROCESS_FLOW_GRID_X
      > (Math.max(...yValues) - Math.min(...yValues)) / PROCESS_FLOW_GRID_Y
  const primaryPosition = (node: BaseNodeModel) => horizontal ? node.x : node.y
  const secondaryPosition = (node: BaseNodeModel) => horizontal ? node.y : node.x
  const nodes = selectedNodes.sort((left, right) => (
    primaryPosition(left) - primaryPosition(right)
    || secondaryPosition(left) - secondaryPosition(right)
  ))
  if (nodes.length < 2) {
    onConnectionError('请先框选至少两个节点')
    return
  }

  const existingEdges = lf.graphModel.edges
  const existingPairs = new Set(
    existingEdges.map(edge => `${edge.sourceNodeId}->${edge.targetNodeId}`),
  )
  const incoming = new Map<string, number>()
  const outgoing = new Map<string, number>()
  const adjacency = new Map<string, Set<string>>()
  existingEdges.forEach((edge) => {
    incoming.set(edge.targetNodeId, (incoming.get(edge.targetNodeId) ?? 0) + 1)
    outgoing.set(edge.sourceNodeId, (outgoing.get(edge.sourceNodeId) ?? 0) + 1)
    adjacency.set(edge.sourceNodeId, new Set([
      ...(adjacency.get(edge.sourceNodeId) ?? []),
      edge.targetNodeId,
    ]))
  })

  const pending: Array<{ sourceNodeId: string; targetNodeId: string }> = []
  for (const source of nodes) {
    const forwardNodes = nodes.filter(
      target => primaryPosition(target) > primaryPosition(source),
    )
    if (!forwardNodes.length) continue
    const nextLayerPosition = Math.min(...forwardNodes.map(primaryPosition))
    const candidates = forwardNodes
      .filter(target => primaryPosition(target) === nextLayerPosition)
      .sort((left, right) => (
        Math.abs(secondaryPosition(left) - secondaryPosition(source))
        - Math.abs(secondaryPosition(right) - secondaryPosition(source))
        || secondaryPosition(left) - secondaryPosition(right)
      ))
    const existingTarget = candidates.find(candidate => (
      existingPairs.has(`${source.id}->${candidate.id}`)
    ))
    if ((outgoing.get(source.id) ?? 0) >= 1) {
      if (existingTarget) continue
      const sourceLabel = source.text.value || source.type
      onConnectionError(`节点“${sourceLabel}”已经连接了其他后续节点`)
      return
    }
    const target = candidates.find((candidate) => {
      const pairKey = `${source.id}->${candidate.id}`
      return !existingPairs.has(pairKey)
        && !batchConnectionError(source, candidate, incoming, outgoing, adjacency)
    })
    if (!target) {
      const firstCandidate = candidates[0]
      if (!firstCandidate) {
        onConnectionError('相邻节点无法连接')
        return
      }
      const error = batchConnectionError(
        source,
        firstCandidate,
        incoming,
        outgoing,
        adjacency,
      )
      onConnectionError(error || '相邻节点无法连接')
      return
    }
    const pairKey = `${source.id}->${target.id}`
    pending.push({ sourceNodeId: source.id, targetNodeId: target.id })
    existingPairs.add(pairKey)
    incoming.set(target.id, (incoming.get(target.id) ?? 0) + 1)
    outgoing.set(source.id, (outgoing.get(source.id) ?? 0) + 1)
    adjacency.set(source.id, new Set([...(adjacency.get(source.id) ?? []), target.id]))
  }
  if (!pending.length) {
    onConnectionError('所选节点之间没有可新增的有效连接')
    return
  }
  addEdges(pending)
}

function batchConnectionError(
  source: BaseNodeModel,
  target: BaseNodeModel,
  incoming: Map<string, number>,
  outgoing: Map<string, number>,
  adjacency: Map<string, Set<string>>,
) {
  const sourceLabel = source.text.value || source.type
  const targetLabel = target.text.value || target.type
  const sourceType = String(source.type)
  const targetType = String(target.type)
  if (sourceType === 'finished_inbound') return `入库节点“${sourceLabel}”不能连接后续节点`
  if (targetType === 'part') return `配件节点“${targetLabel}”不能连接输入线`
  if ((outgoing.get(source.id) ?? 0) >= 1) return `节点“${sourceLabel}”已经有后续节点`
  if (['process', 'qc', 'finished_inbound', 'supplier_processing'].includes(targetType)
    && (incoming.get(target.id) ?? 0) >= 1) {
    return `节点“${targetLabel}”已经有上游节点`
  }
  if (sourceType === 'part' && !['process', 'assembly', 'supplier_processing'].includes(targetType)) {
    return `配件“${sourceLabel}”后只能连接工艺、装配或委外加工节点`
  }
  if (targetType === 'supplier_processing' && sourceType !== 'part') {
    return `委外加工节点“${targetLabel}”的上游必须是配件节点`
  }
  if (sourceType === 'supplier_processing' && targetType !== 'qc') {
    return `委外加工节点“${sourceLabel}”后只能连接QC节点`
  }
  if (sourceType === 'process'
    && targetType !== 'qc'
    && !(source.properties.directInbound === true && targetType === 'finished_inbound')) {
    return `工艺节点“${sourceLabel}”后必须连接QC；装包节点可以直接连接入库`
  }
  if (sourceType === 'assembly' && targetType !== 'qc') {
    return `装配节点“${sourceLabel}”后只能连接QC节点`
  }
  if (targetType === 'qc' && !['process', 'assembly', 'supplier_processing'].includes(sourceType)) {
    return `QC节点“${targetLabel}”的上游必须是工艺、装配或委外加工节点`
  }
  if (sourceType === 'qc' && !['process', 'assembly', 'finished_inbound'].includes(targetType)) {
    return `QC节点“${sourceLabel}”后只能连接工艺、装配或入库节点`
  }
  if (hasPath(adjacency, target.id, source.id)) return '批量连接会形成流程环路'
  return null
}

function hasPath(adjacency: Map<string, Set<string>>, start: string, goal: string) {
  const queue = [start]
  const visited = new Set<string>()
  while (queue.length) {
    const current = queue.shift()!
    if (current === goal) return true
    if (visited.has(current)) continue
    visited.add(current)
    queue.push(...(adjacency.get(current) ?? []))
  }
  return false
}
