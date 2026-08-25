<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { WorkshopRouteOption } from '@/api/organization'
import type { BomItem, FlowEdge, FlowNode, ProcessFlow } from '../domain/types'
import { useLogicFlowInstance } from '../composables/useLogicFlowInstance'
import {
  startPartDrag,
  startProcessDrag,
  startQcDrag,
  startShippingDrag,
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

function dragShipping() {
  if (props.readonly) return
  withInstance(startShippingDrag)
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
  dragShipping,
  focusElement,
  getGraphData: currentFlow,
  renderFlow,
  updateNode,
})
</script>

<template>
  <div class="flow-canvas-shell">
    <div ref="containerRef" class="flow-canvas" :class="{ 'is-readonly': readonly }" />
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
    </div>
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
.display-controls { position: absolute; z-index: 10; top: 78px; right: 15px; display: flex; gap: 6px; padding: 6px; border-radius: 8px; background: color-mix(in srgb, var(--md-surface-container-lowest) 88%, transparent); box-shadow: 0 1px 8px rgb(0 0 0 / 12%); }
.display-control-group { display: flex; align-items: center; gap: 4px; padding-left: 6px; color: var(--el-text-color-secondary); font-size: 12px; }
.display-control-group + .display-control-group { margin-left: 2px; padding-left: 8px; border-left: 1px solid var(--md-outline-variant); }
.display-controls button { width: 32px; height: 32px; padding: 0; border: 1px solid var(--md-outline-variant); border-radius: 7px; color: var(--el-text-color-primary); background: var(--md-surface-container-lowest); cursor: pointer; font-size: 16px; }
.display-controls button:hover { color: var(--el-color-primary); border-color: var(--el-color-primary); }
@media (max-width: 600px) { .flow-canvas { height: 480px; } }
</style>
