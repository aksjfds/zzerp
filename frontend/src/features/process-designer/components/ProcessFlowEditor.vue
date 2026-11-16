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
      <div><h2>流程图</h2></div>
      <div class="heading-actions"><slot name="actions" :disabled="loading || !!error" /></div>
    </div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="loadDepartments" />
    <div class="designer-shell" :class="{ 'has-property': true, 'is-readonly': readonly }">
      <ProcessNodePalette v-if="!readonly" :bom-items="bomItems" :departments="departments" :placed-bom-ids="placedBomIds" :loading="loading" @drag-part="canvas?.dragPart($event)" @add-part="canvas?.addPart($event)" @drag-department="canvas?.dragDepartment($event)" @add-department="canvas?.addDepartment($event)" />
      <div class="canvas-stage">
        <div class="canvas-context"><span>工艺路线画布</span><span>{{ modelValue.nodes.length }} 个节点 <i>·</i> {{ modelValue.edges.length }} 条连线</span><ElTag size="small" :type="readonly ? 'info' : 'primary'">{{ readonly ? '只读查看' : '编辑模式' }}</ElTag></div>
      <ProcessFlowCanvas ref="canvas" :model-value="modelValue" :readonly="readonly" @update:model-value="updateFlow" @select-node="selectedNodeId = $event?.id ?? null" @select-edge="selectedEdgeId = $event?.id ?? null" />
        <div class="canvas-legend"><span><i class="part-key" />配件起点</span><span><i class="department-key" />生产部门</span></div>
      </div>
      <ProcessPropertyPanel :node="selectedNode" :edge="selectedEdge" />
    </div>
  </section>
</template>

<style scoped>
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; }
.section-heading > div:first-child { min-width: 0; }
.heading-actions { display: flex; align-items: center; flex: none; gap: 8px; }
.heading-actions:empty { display: none; }
.heading-actions :deep(.el-button + .el-button) { margin-left: 0; }
h2 { margin: 0 0 5px; font-size: 20px; }
p { margin: 0; color: var(--el-text-color-secondary); font-size: 14px; line-height: 1.5; }
.designer-shell { position: relative; display: grid; grid-template-columns: 220px minmax(0, 1fr); min-height: 620px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); overflow: hidden; }
.designer-shell.has-property { grid-template-columns: 200px minmax(0, 1fr) 200px; }
.designer-shell.is-readonly { grid-template-columns: minmax(0, 1fr); }
.designer-shell.is-readonly.has-property { grid-template-columns: minmax(0, 1fr) 200px; }
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
.canvas-stage { min-width: 0; background: var(--erp-surface-muted); }
.canvas-context { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; min-height: 48px; padding: 12px 16px; border-bottom: 1px solid var(--erp-border); background: var(--erp-surface); font-size: 12px; }.canvas-context > span:first-child { font-weight: 500; margin-right: auto; }.canvas-context > span:nth-child(2) { color: var(--erp-text-muted); }.canvas-context i { margin-inline: 4px; font-style: normal; }
.canvas-legend { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 16px; padding: 12px 16px; border-top: 1px solid var(--erp-border); color: var(--erp-text-muted); background: var(--erp-surface); font-size: 11px; }.canvas-legend > span { display: flex; align-items: center; gap: 6px; }.canvas-legend i { width: 10px; height: 10px; border-radius: 3px; }.part-key { background: var(--erp-primary-soft); border: 1px solid var(--erp-primary); }.department-key { background: var(--erp-surface); border: 1px solid var(--erp-text-muted); }.canvas-legend small { margin-left: auto; }
@media (min-width: 901px) and (max-width: 1180px) { .designer-shell.has-property { grid-template-columns: 180px minmax(0, 1fr); }.designer-shell.is-readonly.has-property { grid-template-columns: minmax(0, 1fr); }.designer-shell :deep(.property-panel) { grid-column: 1 / -1; border-left: 0; border-top: 1px solid var(--erp-border); } }
</style>
