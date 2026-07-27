<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { BomItem, FlowEdge, FlowNode, ProcessFlow } from '../domain/types'
import { useLogicFlowInstance } from '../composables/useLogicFlowInstance'
import {
  startPartDrag,
  startAssemblyDrag,
  startProcessDrag,
  startQcDrag,
  startShippingDrag,
  updateNodeDefinition,
} from '../logicflow/commands'

const props = defineProps<{ modelValue: ProcessFlow; readonly?: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [flow: ProcessFlow]
  selectEdge: [edge: FlowEdge | null]
  selectNode: [node: FlowNode | null]
}>()
const containerRef = ref<HTMLDivElement>()
const { currentFlow, emitChange, instance, renderFlow, setReadonly } = useLogicFlowInstance(containerRef, {
  initialFlow: () => props.modelValue,
  readonly: () => Boolean(props.readonly),
  onChange: (flow) => emit('update:modelValue', flow),
  onConnectionError: (message) => ElMessage.error(message),
  onSelectEdge: (edge) => emit('selectEdge', edge),
  onSelectNode: (node) => emit('selectNode', node),
})

watch(() => props.readonly, value => setReadonly(Boolean(value)))

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

function dragProcess(procedureId: number, procedureName: string) {
  if (props.readonly) return
  withInstance((lf) => startProcessDrag(lf, procedureId, procedureName))
}

function dragAssembly() {
  if (props.readonly) return
  withInstance(startAssemblyDrag)
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
  instance.value.focusOn(elementId)
}

defineExpose({
  dragPart,
  dragAssembly,
  dragProcess,
  dragQc,
  dragShipping,
  focusElement,
  getGraphData: currentFlow,
  renderFlow,
  updateNode,
})
</script>

<template><div ref="containerRef" class="flow-canvas" :class="{ 'is-readonly': readonly }" /></template>

<style scoped>
.flow-canvas { min-width: 0; height: 560px; background: var(--md-surface-container-lowest); }
.flow-canvas.is-readonly { cursor: default; }
@media (max-width: 600px) { .flow-canvas { height: 480px; } }
</style>
