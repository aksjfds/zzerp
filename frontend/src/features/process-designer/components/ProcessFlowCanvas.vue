<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { BomItem, FlowEdge, FlowNode, ProcessFlow, RouteType } from '../domain/types'
import { useLogicFlowInstance } from '../composables/useLogicFlowInstance'
import {
  setQcEdgeRoute,
  startPartDrag,
  startAssemblyDrag,
  startProcessDrag,
  startQcDrag,
  updateNodeDefinition,
} from '../logicflow/commands'

const props = defineProps<{ modelValue: ProcessFlow; readonly?: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [flow: ProcessFlow]
  selectEdge: [edge: FlowEdge | null]
  selectNode: [node: FlowNode | null]
}>()
const containerRef = ref<HTMLDivElement>()
const { currentFlow, emitChange, instance, renderFlow } = useLogicFlowInstance(containerRef, {
  initialFlow: () => props.modelValue,
  onChange: (flow) => emit('update:modelValue', flow),
  onConnectionError: (message) => ElMessage.error(message),
  onSelectEdge: (edge) => emit('selectEdge', edge),
  onSelectNode: (node) => emit('selectNode', node),
})

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

function updateNode(nodeId: string, label: string, property: Parameters<typeof updateNodeDefinition>[3]) {
  if (props.readonly) return
  withInstance((lf) => { updateNodeDefinition(lf, nodeId, label, property); emitChange() })
}

function updateRoute(edgeId: string, routeType: RouteType) {
  if (props.readonly) return
  try {
    withInstance((lf) => { setQcEdgeRoute(lf, edgeId, routeType); emitChange() })
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '无法修改连线')
  }
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
  focusElement,
  getGraphData: currentFlow,
  renderFlow,
  updateNode,
  updateRoute,
})
</script>

<template><div ref="containerRef" class="flow-canvas" :class="{ 'is-readonly': readonly }" /></template>

<style scoped>
.flow-canvas { min-width: 0; height: 560px; background: #fff; }
.flow-canvas.is-readonly { cursor: default; pointer-events: none; }
</style>
