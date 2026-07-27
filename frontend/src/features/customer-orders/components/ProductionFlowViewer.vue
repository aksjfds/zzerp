<script setup lang="ts">
import '@logicflow/core/es/index.css'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import LogicFlow, { PolylineEdge, PolylineEdgeModel } from '@logicflow/core'
import { registerProcessNodes } from '@/shared/process-flow/registerNodes'
import { materialColors } from '@/shared/material/tokens'
import { toLogicFlowData } from '@/shared/process-flow/adapter'
import type { FlowEdge, ProcessFlow } from '@/shared/process-flow/types'
import type { ProductionEdgeStat, ProductionNodeStat } from '../domain/types'

const props = defineProps<{
  flow: ProcessFlow
  stats: ProductionNodeStat[]
  edgeStats: ProductionEdgeStat[]
}>()
const container = ref<HTMLDivElement>()
let instance: LogicFlow | null = null
let resizeObserver: ResizeObserver | null = null
let resizeFrame: number | null = null
type ProductionEdgeState = 'pending' | 'active' | 'done'

const EDGE_STYLE: Record<ProductionEdgeState, Record<string, unknown>> = {
  pending: { stroke: materialColors.outlineVariant, strokeWidth: 2, strokeDasharray: '6 4' },
  active: { stroke: materialColors.warning, strokeWidth: 3, strokeDasharray: '10 5' },
  done: { stroke: materialColors.success, strokeWidth: 3 },
}

const EDGE_ANIMATION_STYLE: Record<string, unknown> = {
  stroke: materialColors.warning,
  strokeDasharray: '14,6',
  strokeDashoffset: '100%',
  animationDuration: '12s',
  animationDirection: 'normal',
}

class ProductionPolylineEdgeModel extends PolylineEdgeModel {
  getEdgeAnimationStyle() {
    const style = super.getEdgeAnimationStyle()
    const properties = this.properties as Record<string, unknown>
    const animationStyle = properties.productionAnimationStyle
    return {
      ...style,
      ...(isRecord(animationStyle) ? animationStyle : {}),
    }
  }
}

function nodeLabel(label: string, stat?: ProductionNodeStat): string {
  if (!stat) return `${label}\n入0 出0`
  if (stat.node_type === 'assembly') {
    return `${label}\n装配${stat.transferred_quantity} 产出${stat.output_quantity}`
  }
  if (stat.node_type === 'part') {
    return `${label}\n投入${stat.entered_quantity} 转出${stat.transferred_quantity}`
  }
  if (stat.node_type === 'shipping') {
    return `${label}\n已发货${stat.entered_quantity}`
  }
  return `${label}\n入${stat.entered_quantity} 出${stat.transferred_quantity} 现${stat.current_quantity}`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function edgeState(
  edge: FlowEdge,
  status: Map<string, ProductionNodeStat>,
  edgeStatus: Map<string, ProductionEdgeStat>,
): ProductionEdgeState {
  const sourceStat = status.get(edge.source_node_id)
  if ((sourceStat?.current_quantity ?? 0) > 0) return 'active'
  if ((edgeStatus.get(edge.id)?.transferred_quantity ?? 0) > 0) return 'done'
  return 'pending'
}

function shouldAnimateEdge(
  edge: FlowEdge,
  status: Map<string, ProductionNodeStat>,
  edgeStatus: Map<string, ProductionEdgeStat>,
): boolean {
  return edgeState(edge, status, edgeStatus) === 'active'
}

function productionFlow(status: Map<string, ProductionNodeStat>): ProcessFlow {
  return {
    ...props.flow,
    nodes: props.flow.nodes.map(node => ({
      ...node,
      label: nodeLabel(node.label, status.get(node.id)),
    })),
    edges: props.flow.edges.map(edge => ({
      ...edge,
      edge_type: 'production-polyline',
    })),
  }
}

function withProductionEdgeStyle(
  data: LogicFlow.GraphConfigData,
  status: Map<string, ProductionNodeStat>,
  edgeStatus: Map<string, ProductionEdgeStat>,
): LogicFlow.GraphConfigData {
  const businessEdges = new Map(props.flow.edges.map(edge => [edge.id, edge]))
  return {
    ...data,
    edges: data.edges?.map(edge => {
      const businessEdge = businessEdges.get(edge.id ?? '')
      const state = businessEdge
        ? edgeState(businessEdge, status, edgeStatus)
        : 'pending'
      const animated = businessEdge
        ? shouldAnimateEdge(businessEdge, status, edgeStatus)
        : false
      return {
        ...edge,
        properties: {
          ...edge.properties,
          productionState: state,
          style: EDGE_STYLE[state],
          productionAnimationStyle: animated ? EDGE_ANIMATION_STYLE : undefined,
        },
      }
    }),
  }
}

function applyEdgeAnimation(
  status: Map<string, ProductionNodeStat>,
  edgeStatus: Map<string, ProductionEdgeStat>,
) {
  if (!instance) return
  props.flow.edges.forEach(edge => {
    if (shouldAnimateEdge(edge, status, edgeStatus)) {
      instance?.openEdgeAnimation(edge.id)
    } else {
      instance?.closeEdgeAnimation(edge.id)
    }
  })
}

function render() {
  if (!instance) return
  const status = new Map(props.stats.map(node => [node.flow_node_id, node]))
  const edgeStatus = new Map(props.edgeStats.map(edge => [edge.flow_edge_id, edge]))
  instance.renderRawData(withProductionEdgeStyle(
    toLogicFlowData(productionFlow(status)),
    status,
    edgeStatus,
  ))
  requestAnimationFrame(() => {
    applyEdgeAnimation(status, edgeStatus)
    instance?.fitView(24, 24)
  })
}

function fitToContainer() {
  if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
  resizeFrame = requestAnimationFrame(() => {
    resizeFrame = null
    if (!instance || !container.value) return
    instance.resize(container.value.clientWidth, container.value.clientHeight)
    instance.fitView(24, 24)
  })
}

onMounted(async () => {
  await nextTick()
  if (!container.value) return
  instance = new LogicFlow({
    container: container.value,
    isSilentMode: true,
    grid: false,
    edgeType: 'polyline',
    stopZoomGraph: true,
    stopScrollGraph: true,
    stopMoveGraph: true,
  })
  registerProcessNodes(instance)
  instance.batchRegister([
    { type: 'production-polyline', view: PolylineEdge, model: ProductionPolylineEdgeModel },
  ])
  render()
  resizeObserver = new ResizeObserver(fitToContainer)
  resizeObserver.observe(container.value)
  fitToContainer()
})

watch(() => [props.flow, props.stats, props.edgeStats], render, { deep: true })
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
  resizeFrame = null
  instance?.destroy()
  instance = null
})
</script>

<template>
  <div class="production-flow-viewer-wrap">
    <div class="production-flow-legend">
      <span><i class="legend-line pending" />未开始</span>
      <span><i class="legend-line active" />进行中</span>
      <span><i class="legend-line done" />已流转</span>
    </div>
    <div ref="container" class="production-flow-viewer" />
  </div>
</template>

<style scoped>
.production-flow-viewer-wrap {
  width: 100%;
}

.production-flow-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.production-flow-legend span {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.legend-line {
  display: inline-block;
  width: 28px;
  height: 0;
  border-top: 3px solid;
}

.legend-line.pending {
  border-color: var(--md-outline-variant);
  border-style: dashed;
}

.legend-line.active {
  border-color: var(--erp-warning);
  border-style: dashed;
}

.legend-line.done {
  border-color: var(--erp-success);
}

.production-flow-viewer {
  width: 100%;
  height: clamp(560px, 70vh, 840px);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--erp-radius);
  background: var(--md-surface-container-lowest);
}
@media (max-width: 760px) {
  .production-flow-legend { gap: 8px 12px; }
  .production-flow-viewer { height: clamp(420px, 65vh, 560px); }
}
</style>
