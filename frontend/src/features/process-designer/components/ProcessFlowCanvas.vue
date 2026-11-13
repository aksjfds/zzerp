<script setup lang="ts">
import FlowDisplayControls from '@/shared/process-flow/FlowDisplayControls.vue'
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type LogicFlow from '@logicflow/core'
import type { ProductionDepartment } from '@/features/production-departments'
import type { BomItem, FlowEdge, FlowNode, ProcessFlow } from '../domain/types'
import { useLogicFlowInstance } from '../composables/useLogicFlowInstance'
import { PROCESS_FLOW_GRID_X } from '@/shared/process-flow/adapter'

const props = defineProps<{ modelValue: ProcessFlow; readonly?: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [flow: ProcessFlow]
  selectEdge: [edge: FlowEdge | null]
  selectNode: [node: FlowNode | null]
}>()
const containerRef = ref<HTMLDivElement>()
const {
  changeFontSize, changeNodeSize, currentFlow, instance, renderFlow, setReadonly,
} = useLogicFlowInstance(containerRef, {
  initialFlow: () => props.modelValue, readonly: () => Boolean(props.readonly),
  onChange: flow => emit('update:modelValue', flow),
  onConnectionError: message => ElMessage.error(message),
  onSelectEdge: edge => emit('selectEdge', edge), onSelectNode: node => emit('selectNode', node),
})
watch(() => props.readonly, value => setReadonly(Boolean(value)))
watch(() => props.modelValue, (flow) => {
  if (!instance.value || JSON.stringify(currentFlow()) === JSON.stringify(flow)) return
  emit('selectNode', null); emit('selectEdge', null); renderFlow(flow)
}, { deep: true })

function partConfig(part: BomItem): LogicFlow.NodeConfig | undefined {
  if (!part.id || props.readonly) return
  if (currentFlow().nodes.some(node => node.type === 'part' && node.bom_item_id === part.id)) {
    ElMessage.warning('该配件已放入流程图')
    return
  }
  return { type: 'part', x: 0, y: 0, text: `${part.part_no} · ${part.part_name}`, properties: { bomItemId: part.id } }
}
function departmentConfig(department: ProductionDepartment): LogicFlow.NodeConfig {
  return { type: 'department', x: 0, y: 0, text: department.name, properties: { departmentCode: department.code } }
}
function dragPart(part: BomItem) {
  const config = partConfig(part)
  if (config) instance.value?.dnd.startDrag(config)
}
function dragDepartment(department: ProductionDepartment) {
  if (!props.readonly) instance.value?.dnd.startDrag(departmentConfig(department))
}
function add(config?: LogicFlow.NodeConfig) {
  const lf = instance.value
  if (!lf || props.readonly || !config) return
  const nodes = currentFlow().nodes
  const x = nodes.length ? Math.max(...nodes.map(node => node.x)) + PROCESS_FLOW_GRID_X : 0
  const node = lf.addNode({ ...config, x, y: 0 })
  lf.selectElementById(node.id)
  lf.focusOn({ id: node.id })
}
function addPart(part: BomItem) { add(partConfig(part)) }
function addDepartment(department: ProductionDepartment) { add(departmentConfig(department)) }
function focusElement(id?: string) {
  if (id && instance.value?.getModelById(id)) {
    instance.value.selectElementById(id)
    instance.value.focusOn({ id })
  }
}
defineExpose({ dragPart, addPart, dragDepartment, addDepartment, focusElement, getGraphData: currentFlow, renderFlow })
</script>

<template>
  <div class="flow-canvas-shell">
    <FlowDisplayControls @font-size="changeFontSize" @node-size="changeNodeSize" />
    <div ref="containerRef" class="flow-canvas" :class="{ 'is-readonly': readonly }" />
  </div>
</template>

<style scoped>
.flow-canvas-shell { position: relative; min-width: 0; }
.flow-canvas { position: relative; min-width: 0; height: clamp(680px, calc(100vh - 180px), 960px); background: var(--md-surface-container-lowest); touch-action: none; }
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
