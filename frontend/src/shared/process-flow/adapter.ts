import type LogicFlow from '@logicflow/core'
import {
  PROCESS_FLOW_SCHEMA_VERSION,
  type FlowEdge,
  type FlowNode,
  type FlowPoint,
  type ProcessFlow,
} from './types'

export const PROCESS_FLOW_GRID_X = 500
export const PROCESS_FLOW_GRID_Y = 250

export function toLogicFlowData(
  flow: ProcessFlow,
): LogicFlow.GraphConfigData {
  const normalizedFlow = normalizeEdgeAnchors(flow)
  return {
    nodes: normalizedFlow.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      x: node.x,
      y: node.y,
      text: node.label_position
        ? { value: node.label, ...node.label_position }
        : node.label,
      zIndex: node.z_index,
      rotate: node.rotation,
      properties: node.type === 'part' ? { bomItemId: node.bom_item_id } : { departmentCode: node.department_code },
    })),
    edges: normalizedFlow.edges.map((edge) => ({
      id: edge.id,
      type: edge.edge_type,
      sourceNodeId: edge.source_node_id,
      targetNodeId: edge.target_node_id,
      sourceAnchorId: edge.source_anchor_id,
      targetAnchorId: edge.target_anchor_id,
      startPoint: edge.start_point,
      endPoint: edge.end_point,
      pointsList: edge.points,
      text: edge.label
        ? edge.label_position
          ? { value: edge.label, ...edge.label_position }
          : edge.label
        : undefined,
      zIndex: edge.z_index,
    })),
  }
}

export function fromLogicFlowData(data: LogicFlow.GraphData): ProcessFlow {
  const nodes = data.nodes.map(toBusinessNode)
  const edges = data.edges.map((edge) => toBusinessEdge(edge, nodes))
  return {
    schema_version: PROCESS_FLOW_SCHEMA_VERSION,
    nodes,
    edges,
  }
}

function toBusinessNode(node: LogicFlow.NodeData): FlowNode {
  const base = {
    id: node.id, x: snapCoordinate(node.x, PROCESS_FLOW_GRID_X),
    y: snapCoordinate(node.y, PROCESS_FLOW_GRID_Y), label: textValue(node.text),
    label_position: textPosition(node.text), z_index: node.zIndex, rotation: node.rotate,
  }
  const properties = node.properties ?? {}
  if (node.type === 'part' && typeof properties.bomItemId === 'number') {
    return { ...base, type: 'part', bom_item_id: properties.bomItemId }
  }
  if (node.type === 'department' && typeof properties.departmentCode === 'string' && properties.departmentCode) {
    return { ...base, type: 'department', department_code: properties.departmentCode }
  }
  throw new Error(`节点类型或来源资料不完整：${node.id}`)
}

function toBusinessEdge(edge: LogicFlow.EdgeData, nodes: FlowNode[]): FlowEdge {
  return normalizeEdgeAnchor({
    id: edge.id,
    edge_type: 'polyline',
    source_node_id: edge.sourceNodeId,
    target_node_id: edge.targetNodeId,
    source_anchor_id: edge.sourceAnchorId,
    target_anchor_id: edge.targetAnchorId,
    start_point: edge.startPoint,
    end_point: edge.endPoint,
    points: edge.pointsList,
    label: textValue(edge.text) || undefined,
    label_position: textPosition(edge.text),
    z_index: edge.zIndex,
  }, nodes)
}

function textValue(text: LogicFlow.TextConfig | string | undefined): string {
  return typeof text === 'string' ? text : text?.value ?? ''
}

function textPosition(text: LogicFlow.TextConfig | string | undefined): FlowPoint | undefined {
  return typeof text === 'object' ? { x: text.x, y: text.y } : undefined
}

function normalizeEdgeAnchors(flow: ProcessFlow): ProcessFlow {
  const nodes = flow.nodes.map((node) => {
    const x = snapCoordinate(node.x, PROCESS_FLOW_GRID_X)
    const y = snapCoordinate(node.y, PROCESS_FLOW_GRID_Y)
    const dx = x - node.x
    const dy = y - node.y
    return {
      ...node,
      x,
      y,
      label_position: node.label_position
        ? {
            x: node.label_position.x + dx,
            y: node.label_position.y + dy,
          }
        : undefined,
    }
  })
  return {
    ...flow,
    nodes,
    edges: flow.edges.map(edge => normalizeEdgeAnchor(edge, nodes)),
  }
}

function snapCoordinate(value: number, unit: number) {
  return Math.round(value / unit) * unit
}

function normalizeEdgeAnchor(edge: FlowEdge, nodes: FlowNode[]): FlowEdge {
  const nodeMap = new Map(nodes.map(node => [node.id, node]))
  const source = nodeMap.get(edge.source_node_id)
  const target = nodeMap.get(edge.target_node_id)
  if (!source || !target) return { ...edge }

  const sourceAnchor = resolveAnchor(source, target, edge.source_anchor_id, edge.start_point)
  const targetAnchor = resolveAnchor(target, source, edge.target_anchor_id, edge.end_point)
  return {
    ...edge,
    source_anchor_id: sourceAnchor.id,
    target_anchor_id: targetAnchor.id,
    start_point: sourceAnchor.point,
    end_point: targetAnchor.point,
    points: normalizeEdgePoints(edge.points, sourceAnchor.point, targetAnchor.point),
  }
}

function resolveAnchor(
  node: FlowNode,
  opposite: FlowNode,
  anchorId?: string,
  referencePoint?: FlowPoint,
): { id: string; point: FlowPoint } {
  const anchors = nodeAnchors(node)
  const matched = anchorId ? anchors.find(anchor => anchor.id === anchorId) : undefined
  if (matched) return matched
  if (referencePoint) return nearestAnchor(anchors, referencePoint)
  return directionalAnchor(anchors, node, opposite)
}

type NodeAnchor = { id: string; point: FlowPoint }
type NodeAnchors = [NodeAnchor, NodeAnchor, NodeAnchor, NodeAnchor]

function nodeAnchors(node: FlowNode): NodeAnchors {
  const size = { halfWidth: 75, halfHeight: 28 }
  return [
    { id: `${node.id}_0`, point: { x: node.x, y: node.y - size.halfHeight } },
    { id: `${node.id}_1`, point: { x: node.x + size.halfWidth, y: node.y } },
    { id: `${node.id}_2`, point: { x: node.x, y: node.y + size.halfHeight } },
    { id: `${node.id}_3`, point: { x: node.x - size.halfWidth, y: node.y } },
  ]
}

function nearestAnchor(
  anchors: NodeAnchor[],
  point: FlowPoint,
): { id: string; point: FlowPoint } {
  return anchors.reduce((best, anchor) => (
    distance(anchor.point, point) < distance(best.point, point) ? anchor : best
  ))
}

function directionalAnchor(
  anchors: NodeAnchors,
  node: FlowNode,
  opposite: FlowNode,
): { id: string; point: FlowPoint } {
  const dx = opposite.x - node.x
  const dy = opposite.y - node.y
  if (Math.abs(dx) >= Math.abs(dy)) {
    return anchors[dx >= 0 ? 1 : 3]
  }
  return anchors[dy >= 0 ? 2 : 0]
}

function normalizeEdgePoints(
  points: FlowPoint[] | undefined,
  startPoint: FlowPoint,
  endPoint: FlowPoint,
): FlowPoint[] | undefined {
  if (!points?.length) return undefined
  if (points.length === 1) return [startPoint, endPoint]
  return [startPoint, ...points.slice(1, -1), endPoint]
}

function distance(a: FlowPoint, b: FlowPoint): number {
  return (a.x - b.x) ** 2 + (a.y - b.y) ** 2
}
