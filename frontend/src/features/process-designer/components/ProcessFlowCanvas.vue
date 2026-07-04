<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { BomItem, FlowEdge, FlowNode, ProcessFlow, RouteType } from '../domain/types'
import { useLogicFlowInstance } from '../composables/useLogicFlowInstance'
import {
  addAssemblyNode,
  addProcessNode,
  addQcNode,
  setQcEdgeRoute,
  startPartDrag,
  updateNodeDefinition,
} from '../logicflow/commands'

const props = defineProps<{ modelValue: ProcessFlow }>()
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
  try {
    withInstance((lf) => startPartDrag(lf, item))
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '无法添加配件节点')
  }
}

function addProcess(label: string) {
  withInstance((lf) => { addProcessNode(lf, label); emitChange() })
}

function addAssembly(outputName: string) {
  withInstance((lf) => { addAssemblyNode(lf, outputName); emitChange() })
}

function addQc() {
  withInstance((lf) => { addQcNode(lf); emitChange() })
}

function updateNode(nodeId: string, label: string, property: Parameters<typeof updateNodeDefinition>[3]) {
  withInstance((lf) => { updateNodeDefinition(lf, nodeId, label, property); emitChange() })
}

function updateRoute(edgeId: string, routeType: RouteType) {
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
  addAssembly,
  addProcess,
  addQc,
  dragPart,
  focusElement,
  getGraphData: currentFlow,
  renderFlow,
  updateNode,
  updateRoute,
})
</script>

<template><div ref="containerRef" class="flow-canvas" /></template>

<style scoped>
.flow-canvas { min-width: 0; height: 560px; background: #fff; }
</style>
