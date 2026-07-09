<script setup lang="ts">
import { onMounted, ref } from 'vue'
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
import { queryProcedures, type ProcedureOption } from '@/api/organization'

type NodeProperty = {
  key: 'processCode' | 'outputName' | 'outputPcs' | 'procedureId'
  value: string | number
} | null
type CanvasApi = {
  dragPart: (item: BomItem) => void
  dragAssembly: () => void
  dragProcess: (procedureId: number, procedureName: string) => void
  dragQc: () => void
  focusElement: (elementId?: string) => void
  getGraphData: () => ProcessFlow
  renderFlow: (flow: ProcessFlow) => void
  updateNode: (nodeId: string, label: string, property: NodeProperty) => void
  updateRoute: (edgeId: string, routeType: RouteType) => void
}

const props = defineProps<{ modelValue: ProcessFlow; bomItems: BomItem[]; readonly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: ProcessFlow] }>()
const canvas = ref<CanvasApi>()
const selectedNode = ref<FlowNode | null>(null)
const selectedEdge = ref<FlowEdge | null>(null)
const procedures = ref<ProcedureOption[]>([])

function updateFlow(flow: ProcessFlow) {
  if (props.readonly) return
  emit('update:modelValue', flow)
}

function dragProcedure(procedure: ProcedureOption) {
  if (props.readonly) return
  canvas.value?.dragProcess(procedure.id, procedure.procedure_name)
}

function updateProcess(label: string, process_code: string) {
  if (props.readonly || selectedNode.value?.type !== 'process') return
  canvas.value?.updateNode(selectedNode.value.id, label, { key: 'processCode', value: process_code })
  selectedNode.value = { ...selectedNode.value, label, process_code }
}

function updateProcedure(procedureId: number) {
  if (props.readonly || selectedNode.value?.type !== 'process') return
  const procedure = procedures.value.find((item) => item.id === procedureId)
  if (!procedure) return
  canvas.value?.updateNode(
    selectedNode.value.id,
    procedure.procedure_name,
    { key: 'procedureId', value: procedureId },
  )
  selectedNode.value = {
    ...selectedNode.value,
    label: procedure.procedure_name,
    procedure_id: procedureId,
  }
}

function updateAssembly(label: string, output_name: string, output_pcs: number) {
  if (props.readonly || selectedNode.value?.type !== 'assembly') return
  canvas.value?.updateNode(selectedNode.value.id, label, { key: 'outputName', value: output_name })
  canvas.value?.updateNode(selectedNode.value.id, label, { key: 'outputPcs', value: output_pcs })
  selectedNode.value = { ...selectedNode.value, label, output_name, output_pcs }
}

function updateRoute(routeType: RouteType) {
  if (props.readonly || !selectedEdge.value) return
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
onMounted(async () => { procedures.value = await queryProcedures() })
</script>

<template>
  <section class="flow-editor">
    <div class="section-heading">
      <div>
        <h2>工序流程配置</h2>
        <p>拖入配件后连接工序和装配节点；选择节点或 QC 连线可编辑属性。</p>
      </div>
    </div>
    <div class="designer-shell" :class="{ 'has-property': !readonly && (selectedNode || selectedEdge), 'is-readonly': readonly }">
      <ProcessNodePalette
        v-if="!readonly"
        :bom-items="bomItems"
        :procedures="procedures"
        @drag-part="canvas?.dragPart($event)"
        @drag-procedure="dragProcedure"
        @drag-assembly="canvas?.dragAssembly()"
        @drag-qc="canvas?.dragQc()"
      />
      <ProcessFlowCanvas
        ref="canvas"
        :model-value="modelValue"
        :readonly="readonly"
        @update:model-value="updateFlow"
        @select-node="selectedNode = $event"
        @select-edge="selectedEdge = $event"
      />
      <ProcessPropertyPanel
        v-if="!readonly && (selectedNode || selectedEdge)"
        :node="selectedNode"
        :edge="selectedEdge"
        :procedures="procedures"
        @update-process="updateProcess"
        @update-procedure="updateProcedure"
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
.designer-shell.is-readonly { grid-template-columns: minmax(0, 1fr); }
@media (max-width: 900px) {
  .designer-shell, .designer-shell.has-property { grid-template-columns: 150px minmax(600px, 1fr); overflow-x: auto; }
  .designer-shell :deep(.property-panel) { display: none; }
}
</style>
