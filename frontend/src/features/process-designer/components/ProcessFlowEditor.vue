<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
import { queryWorkshopRoutes, type WorkshopRouteOption } from '@/api/organization'

type NodeProperty = {
  key: 'outputName' | 'outputPcs' | 'workshopId' | 'departmentCode'
  value: string | number | boolean
} | null
type CanvasApi = {
  dragPart: (item: BomItem) => void
  dragQc: () => void
  dragShipping: () => void
  dragProcess: (
    workshopId: number,
    workshopName: string,
    multiple: boolean,
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
const workshops = ref<WorkshopRouteOption[]>([])
const placedBomIds = computed(() => props.modelValue.nodes.flatMap(node => (
  node.type === 'part' ? [node.bom_item_id] : []
)))

function updateFlow(flow: ProcessFlow) {
  if (props.readonly) return
  emit('update:modelValue', flow)
}

function dragWorkshop(workshop: WorkshopRouteOption) {
  if (props.readonly) return
  canvas.value?.dragProcess(
    workshop.id,
    workshop.workshop_name,
    workshop.input_mode === 'multiple',
    workshop.department_code,
  )
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
onMounted(async () => { workshops.value = await queryWorkshopRoutes() })
</script>

<template>
  <section class="flow-editor">
    <div class="section-heading">
      <div>
        <h2>工序流程配置</h2>
        <p>工程部只配置配件经过的车间和QC节点；具体加工工艺由车间在开工单时选择。</p>
      </div>
      <div class="heading-actions"><slot name="actions" /></div>
    </div>
    <div class="designer-shell" :class="{ 'has-property': selectedNode || selectedEdge, 'is-readonly': readonly }">
      <ProcessNodePalette
        v-if="!readonly"
        :bom-items="bomItems"
        :placed-bom-ids="placedBomIds"
        :workshops="workshops"
        @drag-part="canvas?.dragPart($event)"
        @drag-workshop="dragWorkshop"
        @drag-qc="canvas?.dragQc()"
        @drag-shipping="canvas?.dragShipping()"
      />
      <ProcessFlowCanvas
        ref="canvas"
        :model-value="modelValue"
        :workshops="workshops"
        :readonly="readonly"
        @update:model-value="updateFlow"
        @select-node="selectedNode = $event"
        @select-edge="selectedEdge = $event"
      />
      <ProcessPropertyPanel
        v-if="selectedNode || selectedEdge"
        :node="selectedNode"
        :edge="selectedEdge"
        :workshops="workshops"
        :readonly="readonly"
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
