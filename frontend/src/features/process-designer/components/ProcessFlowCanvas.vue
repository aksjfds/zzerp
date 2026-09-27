<script setup lang="ts">
import FlowDisplayControls from '@/shared/process-flow/FlowDisplayControls.vue'
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { WorkshopRouteOption } from '@/api/organization'
import type { BomItem, FlowEdge, FlowNode, ProcessFlow } from '../domain/types'
import { useLogicFlowInstance } from '../composables/useLogicFlowInstance'
import {
  startPartDrag,
  startProcessDrag,
  startQcDrag,
  startSupplierProcessingDrag,
  startFinishedInboundDrag,
  updateNodeDefinition,
} from '../logicflow/commands'

const props = defineProps<{
  modelValue: ProcessFlow
  workshops: WorkshopRouteOption[]
  readonly?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [flow: ProcessFlow]
  selectEdge: [edge: FlowEdge | null]
  selectNode: [node: FlowNode | null]
}>()
const containerRef = ref<HTMLDivElement>()
const {
  changeFontSize,
  changeNodeSize,
  currentFlow,
  emitChange,
  instance,
  renderFlow,
  setReadonly,
} = useLogicFlowInstance(containerRef, {
  initialFlow: () => props.modelValue,
  readonly: () => Boolean(props.readonly),
  onChange: (flow) => emit('update:modelValue', flow),
  onConnectionError: (message) => ElMessage.error(message),
  onSelectEdge: (edge) => emit('selectEdge', edge),
  onSelectNode: (node) => emit('selectNode', node),
  workshopDepartmentCode: (workshopId) => props.workshops.find(
    workshop => workshop.id === workshopId,
  )?.department_code,
  workshopDirectInbound: (workshopId) => {
    const workshop = props.workshops.find(item => item.id === workshopId)
    return workshop?.department_code === 'assembly' && workshop.input_mode === 'single'
  },
})

watch(() => props.readonly, value => setReadonly(Boolean(value)))
watch(() => props.workshops, () => renderFlow(props.modelValue))

watch(
  () => props.modelValue,
  (flow) => {
    if (!instance.value || JSON.stringify(currentFlow()) === JSON.stringify(flow)) return
    emit('selectNode', null)
    emit('selectEdge', null)
    renderFlow(flow)
  },
  { deep: true },
)

function withInstance(action: (lf: NonNullable<typeof instance.value>) => void) {
  if (instance.value) action(instance.value)
}

function dragPart(item: BomItem) {
  if (props.readonly) return
  try {
    withInstance((lf) => startPartDrag(lf, item))
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '无法添加配件节点')
  }
}

function dragProcess(
  workshopId: number,
  workshopName: string,
  multiple: boolean,
  departmentCode: string,
) {
  if (props.readonly) return
  withInstance((lf) => startProcessDrag(
    lf,
    workshopId,
    workshopName,
    multiple,
    departmentCode,
  ))
}

function dragQc() {
  if (props.readonly) return
  withInstance(startQcDrag)
}

function dragSupplierProcessing() {
  if (props.readonly) return
  withInstance(startSupplierProcessingDrag)
}

function dragFinishedInbound() {
  if (props.readonly) return
  withInstance(startFinishedInboundDrag)
}

function updateNode(nodeId: string, label: string, property: Parameters<typeof updateNodeDefinition>[3]) {
  if (props.readonly) return
  withInstance((lf) => { updateNodeDefinition(lf, nodeId, label, property); emitChange() })
}

function focusElement(elementId?: string) {
  if (!instance.value || !elementId || !instance.value.getModelById(elementId)) return
  instance.value.selectElementById(elementId)
}

defineExpose({
  dragPart,
  dragProcess,
  dragQc,
  dragSupplierProcessing,
  dragFinishedInbound,
  focusElement,
  getGraphData: currentFlow,
  renderFlow,
  updateNode,
})
</script>

<template>
  <div class="flow-canvas-shell">
    <FlowDisplayControls @font-size="changeFontSize" @node-size="changeNodeSize" />
    <div ref="containerRef" class="flow-canvas" :class="{ 'is-readonly': readonly }" />
  </div>
</template>

<style scoped>
.flow-canvas-shell { position: relative; min-width: 0; }
.flow-canvas { position: relative; min-width: 0; height: clamp(680px, calc(100vh - 180px), 960px); background: var(--md-surface-container-lowest); }
.flow-canvas :deep(.lf-node-content text) { font-size: var(--process-node-font-size, 13px); font-weight: 700; text-rendering: geometricPrecision; }
.flow-canvas :deep(.lf-edge path),
.flow-canvas :deep(.lf-node-content > g > rect),
.flow-canvas :deep(.lf-node-content > g > polygon) { vector-effect: non-scaling-stroke; }
.flow-canvas :deep(.lf-anchor) { pointer-events: all; transform: scale(var(--process-node-anchor-scale, 1)); transform-box: fill-box; transform-origin: center; }
.flow-canvas :deep(.lf-node-anchor) { r: 6px; stroke-width: 2px; }
.flow-canvas :deep(.lf-node-anchor-hover) { r: 9px; }
.flow-canvas.is-readonly { cursor: grab; }
.flow-canvas.is-readonly:active { cursor: grabbing; }
.flow-canvas.is-middle-panning { cursor: grabbing; }
.flow-canvas :deep(.process-selection-box) { position: absolute; z-index: 20; pointer-events: none; border: 1px solid var(--el-color-primary); background: color-mix(in srgb, var(--el-color-primary) 12%, transparent); }
@media (max-width: 600px) { .flow-canvas { height: 480px; } }
</style>
