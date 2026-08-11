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
} from '../domain/types'
import { queryProcedures, type ProcedureOption } from '@/api/organization'

type NodeProperty = {
  key: 'processCode' | 'outputName' | 'outputPcs' | 'procedureId' | 'departmentCode'
  value: string | number | boolean
} | null
type CanvasApi = {
  dragPart: (item: BomItem) => void
  dragAssembly: () => void
  dragQc: () => void
  dragShipping: () => void
  dragProcess: (
    procedureId: number,
    procedureName: string,
    inputMode: 'single' | 'multiple',
    departmentCode: string,
  ) => void
  focusElement: (elementId?: string) => void
  getGraphData: () => ProcessFlow
  renderFlow: (flow: ProcessFlow) => void
  updateNode: (nodeId: string, label: string, property: NodeProperty) => void
}

const props = defineProps<{
  modelValue: ProcessFlow
  bomItems: BomItem[]
  readonly?: boolean
}>()
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
  canvas.value?.dragProcess(
    procedure.id,
    procedure.procedure_name,
    procedure.input_mode,
    procedure.department_code,
  )
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
  canvas.value?.updateNode(
    selectedNode.value.id,
    procedure.procedure_name,
    { key: 'departmentCode', value: procedure.department_code },
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
        <p>配件可直接进入生产工艺、采购部外购节点或装配；不同部门之间可以直接流转，也可以按实际需要添加QC，并以“发货”作为流程终点。</p>
      </div>
      <div class="heading-actions"><slot name="actions" /></div>
    </div>
    <div class="designer-shell" :class="{ 'has-property': selectedNode || selectedEdge, 'is-readonly': readonly }">
      <ProcessNodePalette
        v-if="!readonly"
        :bom-items="bomItems"
        :procedures="procedures"
        @drag-part="canvas?.dragPart($event)"
        @drag-procedure="dragProcedure"
        @drag-qc="canvas?.dragQc()"
        @drag-shipping="canvas?.dragShipping()"
        @drag-assembly="canvas?.dragAssembly()"
      />
      <ProcessFlowCanvas
        ref="canvas"
        :model-value="modelValue"
        :procedures="procedures"
        :readonly="readonly"
        @update:model-value="updateFlow"
        @select-node="selectedNode = $event"
        @select-edge="selectedEdge = $event"
      />
      <ProcessPropertyPanel
        v-if="selectedNode || selectedEdge"
        :node="selectedNode"
        :edge="selectedEdge"
        :procedures="procedures"
        :readonly="readonly"
        @update-process="updateProcess"
        @update-procedure="updateProcedure"
        @update-assembly="updateAssembly"
      />
    </div>
  </section>
</template>

<style scoped>
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 14px; }
.section-heading > div:first-child { min-width: 0; }
.heading-actions { display: flex; align-items: center; flex: none; gap: 8px; }
.heading-actions:empty { display: none; }
.heading-actions :deep(.el-button + .el-button) { margin-left: 0; }
h2 { margin: 0 0 5px; font-size: 18px; }
p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.5; }
.designer-shell { position: relative; display: grid; grid-template-columns: 236px minmax(0, 1fr); min-height: 620px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); overflow: hidden; }
.designer-shell.has-property { grid-template-columns: 236px minmax(0, 1fr) 220px; }
.designer-shell.is-readonly { grid-template-columns: minmax(0, 1fr); }
.designer-shell.is-readonly.has-property { grid-template-columns: minmax(0, 1fr) 220px; }
@media (max-width: 900px) {
  .section-heading { flex-direction: column; }
  .heading-actions { width: 100%; justify-content: flex-end; }
  .designer-shell:not(.is-readonly), .designer-shell.has-property:not(.is-readonly) { grid-template-columns: minmax(0, 1fr); }
  .designer-shell.is-readonly, .designer-shell.is-readonly.has-property { grid-template-columns: minmax(0, 1fr); }
  .designer-shell :deep(.property-panel) { border-top: 1px solid var(--md-outline-variant); border-left: 0; }
}
@media (max-width: 600px) {
  .heading-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .heading-actions :deep(.el-button) { width: 100%; margin: 0; }
  .designer-shell { min-height: 480px; border-radius: var(--erp-radius); }
}
</style>
