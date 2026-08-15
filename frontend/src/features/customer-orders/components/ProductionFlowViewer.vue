<script setup lang="ts">
import '@logicflow/core/es/index.css'
import '@logicflow/extension/lib/style/index.css'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import LogicFlow, { PolylineEdge } from '@logicflow/core'
import { Control } from '@logicflow/extension'
import {
  ProcessPolylineEdgeModel,
  registerProcessNodes,
} from '@/shared/process-flow/registerNodes'
import { materialColors } from '@/shared/material/tokens'
import { PROCESS_FLOW_GRID_Y, toLogicFlowData } from '@/shared/process-flow/adapter'
import { updateProcessCanvasScale } from '@/shared/process-flow/nodeTextScale'
import {
  applyProcessNodeScale,
  PROCESS_FLOW_MIN_CANVAS_SCALE,
  PRODUCTION_FLOW_EDGE_WIDTH_STORAGE_KEY,
  PRODUCTION_FLOW_FONT_SIZE_STORAGE_KEY,
  PRODUCTION_FLOW_NODE_SCALE_STORAGE_KEY,
  storedProcessFlowNumber,
} from '@/shared/process-flow/canvasDisplay'
import { queryProcedures } from '@/api/organization'
import type { FlowEdge, FlowNodeType, ProcessFlow } from '@/shared/process-flow/types'
import type { ProductionEdgeStat, ProductionNodeStat } from '../domain/types'

const props = defineProps<{
  flow: ProcessFlow
  stats: ProductionNodeStat[]
  edgeStats: ProductionEdgeStat[]
}>()
const container = ref<HTMLDivElement>()
const popoverAnchor = ref<HTMLElement>()
const popoverVisible = ref(false)
const selectedNodeLabel = ref('')
const selectedNodeType = ref<FlowNodeType>()
const selectedNodeStat = ref<ProductionNodeStat | null>(null)
let instance: LogicFlow | null = null
let resizeObserver: ResizeObserver | null = null
let resizeFrame: number | null = null
let fitFrame: number | null = null
let processDepartments = new Map<number, string>()
let fontSize = storedProcessFlowNumber(PRODUCTION_FLOW_FONT_SIZE_STORAGE_KEY, 13, 10)
let nodeDisplayScale = storedProcessFlowNumber(PRODUCTION_FLOW_NODE_SCALE_STORAGE_KEY, 1, 0.6)
let edgeWidth = storedProcessFlowNumber(PRODUCTION_FLOW_EDGE_WIDTH_STORAGE_KEY, 3, 1)
let canvasPanPoint: { x: number; y: number } | null = null
type ProductionEdgeState = 'pending' | 'active' | 'done'
type ProgressField = { label: string; value: number; danger?: boolean }

const EDGE_STYLE: Record<ProductionEdgeState, Record<string, unknown>> = {
  pending: { stroke: materialColors.outlineVariant, strokeWidth: 3, strokeDasharray: '6 4' },
  active: { stroke: materialColors.warning, strokeWidth: 4, strokeDasharray: '10 5' },
  done: { stroke: materialColors.success, strokeWidth: 4 },
}

const EDGE_ANIMATION_STYLE: Record<string, unknown> = {
  stroke: materialColors.warning,
  strokeDasharray: '14,6',
  strokeDashoffset: '100%',
  animationDuration: '12s',
  animationDirection: 'normal',
}

class ProductionPolylineEdgeModel extends ProcessPolylineEdgeModel {
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

function productionFlow(): ProcessFlow {
  return {
    ...props.flow,
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

function fitFlowToView() {
  if (fitFrame !== null) cancelAnimationFrame(fitFrame)
  fitFrame = requestAnimationFrame(() => {
    fitFrame = null
    if (!instance || !container.value) return
    instance.resize(container.value.clientWidth, container.value.clientHeight)
    instance.fitView(48, 48)
    updateProcessCanvasScale(
      container.value,
      instance.graphModel.transformModel.SCALE_X,
    )
  })
}

function changeFontSize(delta: number) {
  fontSize = Math.max(10, fontSize + delta)
  container.value?.style.setProperty('--process-node-font-size', `${fontSize}px`)
  localStorage.setItem(PRODUCTION_FLOW_FONT_SIZE_STORAGE_KEY, String(fontSize))
}

function changeNodeSize(delta: number) {
  nodeDisplayScale = Math.max(0.6, Number((nodeDisplayScale + delta).toFixed(2)))
  localStorage.setItem(PRODUCTION_FLOW_NODE_SCALE_STORAGE_KEY, String(nodeDisplayScale))
  if (instance) applyProcessNodeScale(instance, nodeDisplayScale)
}

function changeEdgeWidth(delta: number) {
  edgeWidth = Math.max(1, edgeWidth + delta)
  container.value?.style.setProperty('--process-edge-width', `${edgeWidth}px`)
  localStorage.setItem(PRODUCTION_FLOW_EDGE_WIDTH_STORAGE_KEY, String(edgeWidth))
}

function handleCanvasPanStart(event: PointerEvent) {
  if (event.button !== 0 || !instance) return
  const target = event.target
  if (!(target instanceof Element)
    || !target.closest('.lf-canvas-overlay')
    || target.closest('.lf-node, .lf-edge, .lf-control')) return
  closeNodeProgress()
  event.preventDefault()
  event.stopPropagation()
  canvasPanPoint = { x: event.clientX, y: event.clientY }
  container.value?.classList.add('is-canvas-panning')
}

function handleCanvasPanMove(event: PointerEvent) {
  if (!canvasPanPoint || !instance) return
  event.preventDefault()
  instance.translate(
    event.clientX - canvasPanPoint.x,
    event.clientY - canvasPanPoint.y,
  )
  canvasPanPoint = { x: event.clientX, y: event.clientY }
}

function handleCanvasPanEnd(event: PointerEvent) {
  if (event.button !== 0 || !canvasPanPoint) return
  canvasPanPoint = null
  container.value?.classList.remove('is-canvas-panning')
}

function handleOverviewClick(event: MouseEvent) {
  const target = event.target
  const controlItem = target instanceof Element ? target.closest('.lf-control-item') : null
  if (!controlItem?.querySelector('.lf-control-fit')) return
  event.preventDefault()
  event.stopPropagation()
  fitFlowToView()
}

function showNodeProgress(
  nodeId: string,
  event: MouseEvent | PointerEvent | undefined,
) {
  const node = props.flow.nodes.find(item => item.id === nodeId)
  if (!node || !popoverAnchor.value) return
  closeNodeProgress()
  selectedNodeLabel.value = node.label
  selectedNodeType.value = node.type
  selectedNodeStat.value = props.stats.find(item => item.flow_node_id === nodeId) ?? null
  const nodeElement = container.value?.querySelector(`[data-id="${CSS.escape(nodeId)}"]`)
  const rect = nodeElement?.getBoundingClientRect()
  const left = event?.clientX ?? (rect ? rect.left + rect.width / 2 : 0)
  const top = event?.clientY ?? (rect ? rect.top + rect.height / 2 : 0)
  popoverAnchor.value.style.left = `${left}px`
  popoverAnchor.value.style.top = `${top}px`
  nextTick(() => {
    instance?.selectElementById(nodeId)
    popoverVisible.value = true
  })
}

function closeNodeProgress() {
  popoverVisible.value = false
  instance?.clearSelectElements()
}

function handlePopoverVisibleChange(visible: boolean) {
  popoverVisible.value = visible
  if (!visible) instance?.clearSelectElements()
}

function nodeTypeLabel(type: FlowNodeType | undefined) {
  if (type === 'part') return '配件'
  if (type === 'process') return '工艺'
  if (type === 'qc') return 'QC'
  if (type === 'assembly') return '装配'
  if (type === 'shipping') return '发货'
  return '节点'
}

function formatQuantity(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

const nodeStatus = computed(() => {
  const stat = selectedNodeStat.value
  if (!stat) return { label: '未开始', tone: 'pending' }
  if (stat.abnormal_quantity > 0) return { label: '存在异常', tone: 'danger' }
  if (stat.current_quantity > 0) return { label: '进行中', tone: 'active' }
  if (stat.entered_quantity > 0 || stat.transferred_quantity > 0 || stat.output_quantity > 0) {
    return { label: selectedNodeType.value === 'shipping' ? '已发货' : '已流转', tone: 'done' }
  }
  return { label: '未开始', tone: 'pending' }
})

const primaryProgress = computed(() => {
  const stat = selectedNodeStat.value
  const type = selectedNodeType.value
  if (type === 'part') return { label: '当前剩余', value: stat?.current_quantity ?? 0 }
  if (type === 'process') return { label: '当前待加工', value: stat?.current_quantity ?? 0 }
  if (type === 'qc') return { label: '当前待检', value: stat?.current_quantity ?? 0 }
  if (type === 'assembly') return { label: '当前可装配', value: stat?.current_quantity ?? 0 }
  if (type === 'shipping') return { label: '已发货', value: stat?.entered_quantity ?? 0 }
  return { label: '当前数量', value: stat?.current_quantity ?? 0 }
})

const progressFields = computed<ProgressField[]>(() => {
  const stat = selectedNodeStat.value
  if (!stat) return []
  const abnormal = { label: '异常数量', value: stat.abnormal_quantity, danger: stat.abnormal_quantity > 0 }
  if (selectedNodeType.value === 'part') {
    return [
      { label: '投入数量', value: stat.entered_quantity },
      { label: '已转出', value: stat.transferred_quantity },
      abnormal,
    ]
  }
  if (selectedNodeType.value === 'process') {
    return [
      { label: '接收数量', value: stat.entered_quantity },
      { label: '已流转', value: stat.transferred_quantity },
      abnormal,
    ]
  }
  if (selectedNodeType.value === 'qc') {
    return [
      { label: '送检数量', value: stat.entered_quantity },
      { label: '合格数量', value: stat.transferred_quantity },
      abnormal,
    ]
  }
  if (selectedNodeType.value === 'assembly') {
    return [
      { label: '投入数量', value: stat.entered_quantity },
      { label: '装配产出', value: stat.output_quantity },
      { label: '已转出', value: stat.transferred_quantity },
      abnormal,
    ]
  }
  return []
})

const inputDetails = computed(() => Object.entries(selectedNodeStat.value?.input_details ?? {})
  .filter(([, quantity]) => quantity !== 0)
  .map(([name, quantity]) => ({ name, quantity })))

function render() {
  if (!instance) return
  const status = new Map(props.stats.map(node => [node.flow_node_id, node]))
  const edgeStatus = new Map(props.edgeStats.map(edge => [edge.flow_edge_id, edge]))
  instance.renderRawData(withProductionEdgeStyle(
    toLogicFlowData(productionFlow(), {
      processDepartmentCode: procedureId => processDepartments.get(procedureId),
    }),
    status,
    edgeStatus,
  ))
  applyProcessNodeScale(instance, nodeDisplayScale)
  requestAnimationFrame(() => {
    if (container.value && instance) {
      updateProcessCanvasScale(
        container.value,
        instance.graphModel.transformModel.SCALE_X,
      )
    }
    applyEdgeAnimation(status, edgeStatus)
    fitFlowToView()
  })
}

function resizeCanvas() {
  if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
  resizeFrame = requestAnimationFrame(() => {
    resizeFrame = null
    if (!instance || !container.value) return
    fitFlowToView()
  })
}

onMounted(async () => {
  await nextTick()
  if (!container.value) return
  container.value.style.setProperty('--process-node-font-size', `${fontSize}px`)
  container.value.style.setProperty('--process-edge-width', `${edgeWidth}px`)
  try {
    const procedures = await queryProcedures()
    processDepartments = new Map(procedures.map(
      procedure => [procedure.id, procedure.department_code] as const,
    ))
  } catch {
    processDepartments = new Map()
  }
  instance = new LogicFlow({
    container: container.value,
    isSilentMode: true,
    grid: { size: PROCESS_FLOW_GRID_Y, visible: true },
    snapGrid: false,
    edgeType: 'polyline',
    stopZoomGraph: true,
    stopScrollGraph: true,
    stopMoveGraph: true,
    plugins: [Control],
  })
  instance.setZoomMiniSize(PROCESS_FLOW_MIN_CANVAS_SCALE)
  registerProcessNodes(instance)
  container.value.addEventListener('pointerdown', handleCanvasPanStart, true)
  container.value.addEventListener('click', handleOverviewClick, true)
  document.addEventListener('pointermove', handleCanvasPanMove)
  document.addEventListener('pointerup', handleCanvasPanEnd)
  instance.on('graph:transform', ({ transform }) => {
    closeNodeProgress()
    if (container.value && instance) {
      updateProcessCanvasScale(container.value, transform.SCALE_X)
    }
  })
  instance.batchRegister([
    { type: 'production-polyline', view: PolylineEdge, model: ProductionPolylineEdgeModel },
  ])
  instance.on('node:click', ({ data, e }) => {
    showNodeProgress(data.id, e as MouseEvent | undefined)
  })
  instance.on('blank:click', closeNodeProgress)
  render()
  resizeObserver = new ResizeObserver(resizeCanvas)
  resizeObserver.observe(container.value)
  resizeCanvas()
})

watch(() => [props.flow, props.stats, props.edgeStats], render, { deep: true })
onBeforeUnmount(() => {
  container.value?.removeEventListener('pointerdown', handleCanvasPanStart, true)
  container.value?.removeEventListener('click', handleOverviewClick, true)
  document.removeEventListener('pointermove', handleCanvasPanMove)
  document.removeEventListener('pointerup', handleCanvasPanEnd)
  canvasPanPoint = null
  resizeObserver?.disconnect()
  resizeObserver = null
  if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
  resizeFrame = null
  instance?.destroy()
  instance = null
  if (fitFrame !== null) cancelAnimationFrame(fitFrame)
  fitFrame = null
})
</script>

<template>
  <div class="production-flow-viewer-wrap">
    <div class="production-flow-legend">
      <span><i class="legend-line pending" />未开始</span>
      <span><i class="legend-line active" />进行中</span>
      <span><i class="legend-line done" />已流转</span>
    </div>
    <div class="production-flow-canvas-shell">
      <div ref="container" class="production-flow-viewer" />
      <el-popover
        :visible="popoverVisible"
        placement="top"
        :width="320"
        trigger="click"
        popper-class="production-node-progress-popover"
        :fallback-placements="['top', 'right', 'bottom', 'left']"
        @update:visible="handlePopoverVisibleChange"
      >
        <template #reference>
          <span ref="popoverAnchor" class="node-popover-anchor" />
        </template>
        <div class="node-progress-popover">
          <div class="node-progress-header">
            <div>
              <div class="node-progress-title">{{ selectedNodeLabel }}</div>
              <div class="node-progress-type">{{ nodeTypeLabel(selectedNodeType) }}</div>
            </div>
            <span class="node-progress-status" :class="`is-${nodeStatus.tone}`">
              {{ nodeStatus.label }}
            </span>
          </div>

          <template v-if="selectedNodeStat">
            <div class="node-progress-primary">
              <span>{{ primaryProgress.label }}</span>
              <strong>{{ formatQuantity(primaryProgress.value) }}</strong>
            </div>
            <div class="node-progress-grid">
              <template v-for="field in progressFields" :key="field.label">
                <span>{{ field.label }}</span>
                <strong :class="{ 'is-danger': field.danger, 'is-zero': field.value === 0 }">
                  {{ formatQuantity(field.value) }}
                </strong>
              </template>
            </div>
            <details v-if="inputDetails.length" class="node-input-details">
              <summary>来源明细（{{ inputDetails.length }}）</summary>
              <div class="node-input-list">
                <template v-for="item in inputDetails" :key="item.name">
                  <span>{{ item.name }}</span>
                  <strong>{{ formatQuantity(item.quantity) }}</strong>
                </template>
              </div>
            </details>
          </template>
          <div v-else class="node-progress-empty">暂无生产记录</div>
        </div>
      </el-popover>
      <div class="display-controls" aria-label="节点显示大小">
        <div class="display-control-group">
          <span>字体</span>
          <button type="button" aria-label="缩小字体" title="缩小字体" @click="changeFontSize(-1)">−</button>
          <button type="button" aria-label="放大字体" title="放大字体" @click="changeFontSize(1)">＋</button>
        </div>
        <div class="display-control-group">
          <span>节点</span>
          <button type="button" aria-label="缩小节点" title="缩小节点" @click="changeNodeSize(-0.1)">−</button>
          <button type="button" aria-label="放大节点" title="放大节点" @click="changeNodeSize(0.1)">＋</button>
        </div>
        <div class="display-control-group">
          <span>连线</span>
          <button type="button" aria-label="变细连线" title="变细连线" @click="changeEdgeWidth(-1)">−</button>
          <button type="button" aria-label="加粗连线" title="加粗连线" @click="changeEdgeWidth(1)">＋</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.production-flow-viewer-wrap {
  width: 100%;
}

.production-flow-canvas-shell {
  position: relative;
  min-width: 0;
}

.node-popover-anchor {
  position: fixed;
  z-index: -1;
  width: 1px;
  height: 1px;
  pointer-events: none;
}

.node-progress-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.node-progress-title { color: var(--el-text-color-primary); font-size: 16px; font-weight: 700; line-height: 1.35; }
.node-progress-type { margin-top: 3px; color: var(--el-text-color-secondary); font-size: 12px; }
.node-progress-status { flex: none; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.node-progress-status.is-pending { color: var(--el-text-color-secondary); background: var(--md-surface-container); }
.node-progress-status.is-active { color: var(--erp-warning); background: color-mix(in srgb, var(--erp-warning) 12%, transparent); }
.node-progress-status.is-done { color: var(--erp-success); background: color-mix(in srgb, var(--erp-success) 12%, transparent); }
.node-progress-status.is-danger { color: var(--el-color-danger); background: color-mix(in srgb, var(--el-color-danger) 12%, transparent); }
.node-progress-primary { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-top: 14px; padding: 12px 14px; border-radius: 10px; background: var(--md-surface-container-low); }
.node-progress-primary span { color: var(--el-text-color-secondary); font-size: 13px; }
.node-progress-primary strong { color: var(--el-color-primary); font-size: 24px; font-variant-numeric: tabular-nums; line-height: 1; }
.node-progress-grid { display: grid; grid-template-columns: 1fr auto; gap: 9px 20px; margin-top: 14px; padding: 0 2px; }
.node-progress-grid span { color: var(--el-text-color-secondary); }
.node-progress-grid strong { color: var(--el-text-color-primary); font-variant-numeric: tabular-nums; text-align: right; }
.node-progress-grid strong.is-zero { color: var(--el-text-color-placeholder); font-weight: 500; }
.node-progress-grid strong.is-danger { color: var(--el-color-danger); font-weight: 700; }
.node-input-details { margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--md-outline-variant); }
.node-input-details summary { color: var(--el-text-color-regular); cursor: pointer; font-size: 13px; font-weight: 600; }
.node-input-list { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 7px 16px; margin-top: 10px; }
.node-input-list span { overflow: hidden; color: var(--el-text-color-secondary); text-overflow: ellipsis; white-space: nowrap; }
.node-input-list strong { font-variant-numeric: tabular-nums; text-align: right; }
.node-progress-empty { margin-top: 14px; padding: 18px 12px; border-radius: 10px; color: var(--el-text-color-secondary); background: var(--md-surface-container-low); text-align: center; }

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
  cursor: grab;
}
.production-flow-viewer :deep(.lf-node-content text) { pointer-events: none; user-select: none; cursor: inherit; font-size: var(--process-node-font-size, 13px); font-weight: 700; text-rendering: geometricPrecision; }
.production-flow-viewer :deep(.lf-edge > g:first-child polyline) { stroke-width: var(--process-edge-width, 3px) !important; }
.production-flow-viewer :deep(.lf-edge path),
.production-flow-viewer :deep(.lf-edge polyline),
.production-flow-viewer :deep(.lf-node-content > g > rect),
.production-flow-viewer :deep(.lf-node-content > g > polygon) { vector-effect: non-scaling-stroke; }
.production-flow-viewer :deep(.lf-anchor) { pointer-events: all; transform: scale(var(--process-node-anchor-scale, 1)); transform-box: fill-box; transform-origin: center; }
.production-flow-viewer :deep(.lf-node) { cursor: pointer; }
.production-flow-viewer.is-canvas-panning { cursor: grabbing; }
.display-controls { position: absolute; z-index: 10; top: 78px; right: 15px; display: flex; gap: 6px; padding: 6px; border-radius: 8px; background: color-mix(in srgb, var(--md-surface-container-lowest) 88%, transparent); box-shadow: 0 1px 8px rgb(0 0 0 / 12%); }
.display-control-group { display: flex; align-items: center; gap: 4px; padding-left: 6px; color: var(--el-text-color-secondary); font-size: 12px; }
.display-control-group + .display-control-group { margin-left: 2px; padding-left: 8px; border-left: 1px solid var(--md-outline-variant); }
.display-controls button { width: 32px; height: 32px; padding: 0; border: 1px solid var(--md-outline-variant); border-radius: 7px; color: var(--el-text-color-primary); background: var(--md-surface-container-lowest); cursor: pointer; font-size: 16px; }
.display-controls button:hover { color: var(--el-color-primary); border-color: var(--el-color-primary); }
@media (max-width: 760px) {
  .production-flow-legend { gap: 8px 12px; }
  .production-flow-viewer { height: clamp(420px, 65vh, 560px); }
}
</style>
