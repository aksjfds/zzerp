<script setup lang="ts">
import { ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import '@logicflow/core/es/index.css'
import '@logicflow/extension/lib/style/index.css'
import ProcessFlowCanvas from './ProcessFlowCanvas.vue'
import ProcessNodePalette from './ProcessNodePalette.vue'
import ProcessPropertyPanel from './ProcessPropertyPanel.vue'
import type {
  BomItem,
  FlowEdge,
  FlowNode,
  ProcessFlow,
  RouteType,
} from '../domain/types'

type NodeProperty = { key: 'processCode' | 'outputName'; value: string } | null
type CanvasApi = {
  addAssembly: (outputName: string) => void
  addProcess: (label: string) => void
  addQc: () => void
  dragPart: (item: BomItem) => void
  focusElement: (elementId?: string) => void
  getGraphData: () => ProcessFlow
  renderFlow: (flow: ProcessFlow) => void
  updateNode: (nodeId: string, label: string, property: NodeProperty) => void
  updateRoute: (edgeId: string, routeType: RouteType) => void
}

const props = defineProps<{ modelValue: ProcessFlow; bomItems: BomItem[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: ProcessFlow] }>()
const canvas = ref<CanvasApi>()
const selectedNode = ref<FlowNode | null>(null)
const selectedEdge = ref<FlowEdge | null>(null)

function updateFlow(flow: ProcessFlow) {
  emit('update:modelValue', flow)
}

async function promptProcess() {
  try {
    const { value } = await ElMessageBox.prompt('请输入工序名称，例如 CNC、粗光、电镀', '添加工序', {
      inputPattern: /\S+/,
      inputErrorMessage: '工序名称不能为空',
    })
    canvas.value?.addProcess(value.trim())
  } catch { /* 用户取消 */ }
}

async function promptAssembly() {
  try {
    const { value } = await ElMessageBox.prompt('请输入该节点产出的装配体名称', '添加装配节点', {
      inputPattern: /\S+/,
      inputErrorMessage: '装配体名称不能为空',
    })
    canvas.value?.addAssembly(value.trim())
  } catch { /* 用户取消 */ }
}

function updateProcess(label: string, process_code: string) {
  if (selectedNode.value?.type !== 'process') return
  canvas.value?.updateNode(selectedNode.value.id, label, { key: 'processCode', value: process_code })
  selectedNode.value = { ...selectedNode.value, label, process_code }
}

function updateAssembly(label: string, output_name: string) {
  if (selectedNode.value?.type !== 'assembly') return
  canvas.value?.updateNode(selectedNode.value.id, label, { key: 'outputName', value: output_name })
  selectedNode.value = { ...selectedNode.value, label, output_name }
}

function updateRoute(routeType: RouteType) {
  if (!selectedEdge.value) return
  canvas.value?.updateRoute(selectedEdge.value.id, routeType)
  selectedEdge.value = {
    ...selectedEdge.value,
    route_type: routeType,
    outcome: routeType === 'rework' ? 'rejected' : 'approved',
    label: routeType === 'rework' ? '不合格返工' : '合格',
  }
}

function graphData() {
  return canvas.value?.getGraphData() ?? props.modelValue
}

function focusElement(elementId?: string) {
  canvas.value?.focusElement(elementId)
}

function reload(flow: ProcessFlow) {
  selectedNode.value = null
  selectedEdge.value = null
  canvas.value?.renderFlow(flow)
  emit('update:modelValue', flow)
}

defineExpose({ focusElement, getGraphData: graphData, reload })
</script>

<template>
  <section class="flow-editor">
    <div class="section-heading">
      <div>
        <h2>工序流程配置</h2>
        <p>拖入配件后连接工序和装配节点；选择节点或 QC 连线可编辑属性。</p>
      </div>
    </div>
    <div class="designer-shell" :class="{ 'has-property': selectedNode || selectedEdge }">
      <ProcessNodePalette
        :bom-items="bomItems"
        @drag-part="canvas?.dragPart($event)"
        @add-process="promptProcess"
        @add-assembly="promptAssembly"
        @add-qc="canvas?.addQc()"
      />
      <ProcessFlowCanvas
        ref="canvas"
        :model-value="modelValue"
        @update:model-value="updateFlow"
        @select-node="selectedNode = $event"
        @select-edge="selectedEdge = $event"
      />
      <ProcessPropertyPanel
        v-if="selectedNode || selectedEdge"
        :node="selectedNode"
        :edge="selectedEdge"
        @update-process="updateProcess"
        @update-assembly="updateAssembly"
        @update-route="updateRoute"
      />
    </div>
  </section>
</template>

<style scoped>
.section-heading { margin-bottom: 14px; }
h2 { margin: 0 0 5px; font-size: 18px; }
p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.5; }
.designer-shell { display: grid; grid-template-columns: 190px minmax(0, 1fr); min-height: 560px; border: 1px solid var(--erp-border); border-radius: 8px; overflow: hidden; }
.designer-shell.has-property { grid-template-columns: 190px minmax(0, 1fr) 220px; }
@media (max-width: 900px) {
  .designer-shell, .designer-shell.has-property { grid-template-columns: 150px minmax(600px, 1fr); overflow-x: auto; }
  .designer-shell :deep(.property-panel) { display: none; }
}
</style>
