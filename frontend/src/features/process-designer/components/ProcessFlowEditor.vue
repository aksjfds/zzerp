<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import '@logicflow/core/es/index.css'
import '@logicflow/extension/lib/style/index.css'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryProductionDepartments, type ProductionDepartment } from '@/features/production-departments'
import ProcessFlowCanvas from './ProcessFlowCanvas.vue'
import ProcessNodePalette from './ProcessNodePalette.vue'
import ProcessPropertyPanel from './ProcessPropertyPanel.vue'
import type { BomItem, ProcessFlow } from '../domain/types'

const props = defineProps<{ modelValue: ProcessFlow; bomItems: BomItem[]; readonly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: ProcessFlow] }>()
const canvas = ref<InstanceType<typeof ProcessFlowCanvas>>()
const selectedNodeId = ref<string | null>(null)
const selectedEdgeId = ref<string | null>(null)
const departments = ref<ProductionDepartment[]>([])
const loading = ref(false)
const error = ref('')
let active = true
let revision = 0
const selectedNode = computed(() => props.modelValue.nodes.find(node => node.id === selectedNodeId.value) ?? null)
const selectedEdge = computed(() => props.modelValue.edges.find(edge => edge.id === selectedEdgeId.value) ?? null)
const placedBomIds = computed(() => props.modelValue.nodes.flatMap(node => node.type === 'part' ? [node.bom_item_id] : []))
async function loadDepartments() {
  const current = ++revision
  loading.value = true; error.value = ''
  try {
    const result = await queryProductionDepartments()
    if (active && current === revision) departments.value = result
  } catch (cause) {
    if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '生产部门加载失败'
  } finally { if (active && current === revision) loading.value = false }
}
function updateFlow(flow: ProcessFlow) { if (!props.readonly) emit('update:modelValue', flow) }
function graphData() { return canvas.value?.getGraphData() ?? props.modelValue }
function focusElement(id?: string) { canvas.value?.focusElement(id) }
function reload(flow: ProcessFlow) {
  selectedNodeId.value = null; selectedEdgeId.value = null
  canvas.value?.renderFlow(flow); emit('update:modelValue', flow)
}
defineExpose({ focusElement, getGraphData: graphData, reload })
onMounted(loadDepartments)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>

<template>
  <section class="flow-editor">
    <div class="section-heading">
      <div><h2>流程图</h2><p>将配件节点连接到部门节点，连线表示配件经过的部门。</p></div>
      <div class="heading-actions"><slot name="actions" :disabled="loading || !!error" /></div>
    </div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="loadDepartments" />
    <div class="designer-shell" :class="{ 'has-property': selectedNode || selectedEdge, 'is-readonly': readonly }">
      <ProcessNodePalette v-if="!readonly" :bom-items="bomItems" :departments="departments" :placed-bom-ids="placedBomIds" :loading="loading" @drag-part="canvas?.dragPart($event)" @add-part="canvas?.addPart($event)" @drag-department="canvas?.dragDepartment($event)" @add-department="canvas?.addDepartment($event)" />
      <ProcessFlowCanvas ref="canvas" :model-value="modelValue" :readonly="readonly" @update:model-value="updateFlow" @select-node="selectedNodeId = $event?.id ?? null" @select-edge="selectedEdgeId = $event?.id ?? null" />
      <ProcessPropertyPanel v-if="selectedNode || selectedEdge" :node="selectedNode" :edge="selectedEdge" />
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
.designer-shell { position: relative; display: grid; grid-template-columns: 220px minmax(0, 1fr); min-height: 620px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); overflow: hidden; }
.designer-shell.has-property { grid-template-columns: 220px minmax(0, 1fr) 220px; }
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
