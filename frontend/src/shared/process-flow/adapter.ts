import type LogicFlow from '@logicflow/core'
import {
  PROCESS_FLOW_SCHEMA_VERSION,
  type FlowEdge,
  type FlowNode,
  type FlowNodeType,
  type FlowPoint,
  type ProcessFlow,
} from './types'

const NODE_TYPES = new Set<FlowNodeType>(['part', 'process', 'assembly', 'qc'])

export function toLogicFlowData(flow: ProcessFlow): LogicFlow.GraphConfigData {
  return {
    nodes: flow.nodes.map((node) => ({
      id: node.id,
      type: node.type,
      x: node.x,
      y: node.y,
      text: node.label_position
        ? { value: node.label, ...node.label_position }
        : node.label,
      zIndex: node.z_index,
      rotate: node.rotation,
      properties: nodeProperties(node),
    })),
    edges: flow.edges.map((edge) => ({
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
      properties: { routeType: edge.route_type, outcome: edge.outcome },
    })),
  }
}

export function fromLogicFlowData(data: LogicFlow.GraphData): ProcessFlow {
  return {
    schema_version: PROCESS_FLOW_SCHEMA_VERSION,
    nodes: data.nodes.map(toBusinessNode),
    edges: data.edges.map(toBusinessEdge),
  }
}

function toBusinessNode(node: LogicFlow.NodeData): FlowNode {
  if (!NODE_TYPES.has(node.type as FlowNodeType)) {
    throw new Error(`Unsupported LogicFlow node type: ${node.type}`)
  }
  const type = node.type as FlowNodeType
  const properties = node.properties ?? {}
  const base = {
    id: node.id,
    type,
    x: node.x,
    y: node.y,
    label: textValue(node.text),
    label_position: textPosition(node.text),
    z_index: node.zIndex,
    rotation: node.rotate,
  }
  if (type === 'part') {
    return {
      ...base,
      type,
      bom_item_id: requiredNumber(properties.bomItemId, 'bomItemId'),
      part_no: requiredString(properties.partNo, 'partNo'),
    }
  }
  if (type === 'process') {
    return {
      ...base,
      type,
      process_code: stringValue(properties.processCode),
      procedure_id: requiredNumber(properties.procedureId, 'procedureId'),
    }
  }
  if (type === 'assembly') {
    return {
      ...base,
      type,
      output_name: stringValue(properties.outputName),
      output_pcs: requiredNumber(properties.outputPcs ?? 1, 'outputPcs'),
    }
  }
  return { ...base, type: 'qc' }
}

function toBusinessEdge(edge: LogicFlow.EdgeData): FlowEdge {
  const properties = edge.properties ?? {}
  return {
    id: edge.id,
    edge_type: edge.type,
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
    route_type: properties.routeType === 'rework' ? 'rework' : 'normal',
    outcome: properties.outcome === 'approved' || properties.outcome === 'rejected'
      ? properties.outcome
      : undefined,
  }
}

function nodeProperties(node: FlowNode): Record<string, unknown> {
  if (node.type === 'part') return { bomItemId: node.bom_item_id, partNo: node.part_no }
  if (node.type === 'process') {
    return { processCode: node.process_code, procedureId: node.procedure_id }
  }
  if (node.type === 'assembly') {
    return { outputName: node.output_name, outputPcs: node.output_pcs }
  }
  return {}
}

function textValue(text: LogicFlow.TextConfig | string | undefined): string {
  return typeof text === 'string' ? text : text?.value ?? ''
}

function textPosition(text: LogicFlow.TextConfig | string | undefined): FlowPoint | undefined {
  return typeof text === 'object' ? { x: text.x, y: text.y } : undefined
}

function requiredString(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`Missing ${field}`)
  return value
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function requiredNumber(value: unknown, field: string): number {
  if (typeof value !== 'number') throw new Error(`Missing ${field}`)
  return value
}
