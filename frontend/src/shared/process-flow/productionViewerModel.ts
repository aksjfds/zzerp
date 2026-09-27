import type LogicFlow from '@logicflow/core'
import type { FlowColors } from '@/shared/theme/flowColors'
import type { FlowEdge, FlowNodeType, ProcessFlow } from './types'
import type { ProductionEdgeStat, ProductionNodeStat } from './productionProgress'

type ProductionEdgeState = 'pending' | 'active' | 'done'
export type ProgressField = { label: string; value: number; danger?: boolean }

function edgeState(
  edge: FlowEdge,
  status: Map<string, ProductionNodeStat>,
  edgeStatus: Map<string, ProductionEdgeStat>,
): ProductionEdgeState {
  if ((status.get(edge.source_node_id)?.current_quantity ?? 0) > 0) return 'active'
  if ((edgeStatus.get(edge.id)?.transferred_quantity ?? 0) > 0) return 'done'
  return 'pending'
}

export function shouldAnimateEdge(
  edge: FlowEdge,
  status: Map<string, ProductionNodeStat>,
  edgeStatus: Map<string, ProductionEdgeStat>,
) {
  return edgeState(edge, status, edgeStatus) === 'active'
}

export function buildProductionFlow(flow: ProcessFlow): ProcessFlow {
  return {
    ...flow,
    edges: flow.edges.map(edge => ({ ...edge, edge_type: 'production-polyline' })),
  }
}

export function withProductionEdgeStyle(
  data: LogicFlow.GraphConfigData,
  flow: ProcessFlow,
  status: Map<string, ProductionNodeStat>,
  edgeStatus: Map<string, ProductionEdgeStat>,
  colors: FlowColors,
): LogicFlow.GraphConfigData {
  const edgeStyles: Record<ProductionEdgeState, Record<string, unknown>> = {
    pending: { stroke: colors.outlineVariant, strokeWidth: 3, strokeDasharray: '6 4' },
    active: { stroke: colors.warning, strokeWidth: 4, strokeDasharray: '10 5' },
    done: { stroke: colors.success, strokeWidth: 4 },
  }
  const animationStyle = {
    stroke: colors.warning,
    strokeDasharray: '14,6',
    strokeDashoffset: '100%',
    animationDuration: '12s',
    animationDirection: 'normal',
  }
  const businessEdges = new Map(flow.edges.map(edge => [edge.id, edge]))
  return {
    ...data,
    edges: data.edges?.map((edge) => {
      const businessEdge = businessEdges.get(edge.id ?? '')
      const state = businessEdge ? edgeState(businessEdge, status, edgeStatus) : 'pending'
      const animated = businessEdge ? shouldAnimateEdge(businessEdge, status, edgeStatus) : false
      return {
        ...edge,
        properties: {
          ...edge.properties,
          productionState: state,
          style: edgeStyles[state],
          productionAnimationStyle: animated ? animationStyle : undefined,
        },
      }
    }),
  }
}

export function nodeTypeLabel(type?: FlowNodeType) {
  if (type === 'part') return '配件'
  if (type === 'process') return '工艺'
  if (type === 'supplier_processing') return '委外加工'
  if (type === 'qc') return 'QC'
  if (type === 'assembly') return '装配'
  if (type === 'finished_inbound') return '入库'
  return '节点'
}

export function formatQuantity(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

export function nodeStatus(stat: ProductionNodeStat | null, type?: FlowNodeType) {
  if (!stat) return { label: '未开始', tone: 'pending' }
  if (stat.abnormal_quantity > 0) return { label: '存在异常', tone: 'danger' }
  if (stat.current_quantity > 0) return { label: '进行中', tone: 'active' }
  if (type === 'finished_inbound' && stat.pending_receipt_quantity > 0) {
    return { label: '待入库', tone: 'active' }
  }
  if (type === 'finished_inbound' && stat.received_quantity > 0) {
    return { label: '已入库', tone: 'done' }
  }
  if (stat.entered_quantity > 0 || stat.transferred_quantity > 0 || stat.output_quantity > 0) {
    return { label: '已流转', tone: 'done' }
  }
  return { label: '未开始', tone: 'pending' }
}

export function primaryProgress(stat: ProductionNodeStat | null, type?: FlowNodeType) {
  if (type === 'part') return { label: '当前剩余', value: stat?.current_quantity ?? 0 }
  if (type === 'process') return { label: '当前待加工', value: stat?.current_quantity ?? 0 }
  if (type === 'supplier_processing') return { label: '剩余待合格', value: stat?.current_quantity ?? 0 }
  if (type === 'qc') return { label: '当前待检', value: stat?.current_quantity ?? 0 }
  if (type === 'assembly') return { label: '当前可装配', value: stat?.current_quantity ?? 0 }
  if (type === 'finished_inbound') {
    return { label: '待入库', value: stat?.pending_receipt_quantity ?? 0 }
  }
  return { label: '当前数量', value: stat?.current_quantity ?? 0 }
}

export function progressFields(stat: ProductionNodeStat | null, type?: FlowNodeType): ProgressField[] {
  if (!stat) return []
  const abnormal = { label: '异常数量', value: stat.abnormal_quantity, danger: stat.abnormal_quantity > 0 }
  if (type === 'part') return [{ label: '投入数量', value: stat.entered_quantity }, { label: '已转出', value: stat.transferred_quantity }, abnormal]
  if (type === 'process') return [{ label: '接收数量', value: stat.entered_quantity }, { label: '已流转', value: stat.transferred_quantity }, abnormal]
  if (type === 'supplier_processing') return [{ label: '任务数量', value: stat.entered_quantity }, { label: '累计质检', value: stat.transferred_quantity }, abnormal]
  if (type === 'qc') return [{ label: '送检数量', value: stat.entered_quantity }, { label: '合格数量', value: stat.transferred_quantity }, abnormal]
  if (type === 'assembly') return [{ label: '投入数量', value: stat.entered_quantity }, { label: '装配产出', value: stat.output_quantity }, { label: '已转出', value: stat.transferred_quantity }, abnormal]
  if (type === 'finished_inbound') {
    return [{ label: '已入库', value: stat.received_quantity }]
  }
  return []
}

export function inputDetails(stat: ProductionNodeStat | null) {
  return Object.entries(stat?.input_details ?? {})
    .filter(([, quantity]) => quantity !== 0)
    .map(([name, quantity]) => ({ name, quantity }))
}
