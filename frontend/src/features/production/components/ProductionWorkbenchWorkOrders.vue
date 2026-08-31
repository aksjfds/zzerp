<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ProductionWorkbenchWorkOrder } from '../domain/productionWorkbench'
import type { WorkOrder, WorkOrderBatch } from '../domain/types'
import type { WorkOrderMode } from '../domain/workOrderCardPolicy'
import { assemblyWorkOrderCardPolicy } from '../domain/assemblyWorkOrderCardPolicy'
import { productionWorkOrderCardPolicy as policy } from '../domain/productionWorkOrderCardPolicy'
import PolishWorkOrderPrintDialog from './PolishWorkOrderPrintDialog.vue'
import WorkOrderPrintDialog from './WorkOrderPrintDialog.vue'

const props = withDefaults(defineProps<{
  items: ProductionWorkbenchWorkOrder[]
  loading: boolean
  specialPrinting: boolean
  mode?: WorkOrderMode
}>(), { mode: 'production' })
const emit = defineEmits<{
  submitQc: [item: WorkOrder]
  submitDirectResult: [item: WorkOrder]
  resubmitQc: [item: WorkOrder, batch: WorkOrderBatch]
  cancel: [item: WorkOrder]
  undo: [item: WorkOrder]
}>()
const drawerVisible = ref(false)
const selectedWorkOrderId = ref<number>()
const retainedWorkOrder = ref<ProductionWorkbenchWorkOrder>()
const printVisible = ref(false)
const printItem = ref<WorkOrder>()
const selectedWorkOrder = computed(() => (
  props.items.find(item => item.id === selectedWorkOrderId.value) || retainedWorkOrder.value
))
const policies = {
  production: policy,
  assembly: assemblyWorkOrderCardPolicy,
}
const activePolicy = computed(() => policies[props.mode])

watch(() => props.items, (items) => {
  if (!selectedWorkOrderId.value) return
  if (items.some(item => item.id === selectedWorkOrderId.value)) return
  drawerVisible.value = false
  selectedWorkOrderId.value = undefined
  retainedWorkOrder.value = undefined
})

function openDetails(item: ProductionWorkbenchWorkOrder) {
  selectedWorkOrderId.value = item.id
  retainedWorkOrder.value = item
  drawerVisible.value = true
}

function openPrint(item: WorkOrder) {
  printItem.value = item
  printVisible.value = true
}

function batchSequence(item: WorkOrder, batchId: number) {
  const index = item.batches.findIndex(batch => batch.id === batchId)
  return index >= 0 ? index + 1 : '—'
}

function qcResultText(batch: WorkOrderBatch) {
  if (!batch.recorded_at) return '等待 QC'
  const hasRework = Boolean(batch.rework_quantity)
  const hasLoss = Boolean(batch.scrap_quantity || batch.lost_quantity)
  if (hasRework && hasLoss) return '混合异常'
  if (hasLoss) return '含报废/遗失'
  if (hasRework) return '含返工'
  return '已检验'
}
</script>

<template>
  <section v-loading="loading" class="work-orders-section">
    <header><h3>关联工单</h3><span>点击工单查看质检记录和操作</span></header>
    <div v-if="items.length" class="compact-work-orders">
      <button v-for="item in items" :key="item.id" type="button" @click="openDetails(item)">
        <span class="order-name">
          <strong>{{ item.is_temporary ? '临时工单' : '工单' }} {{ item.work_order_no }}</strong>
          <small>{{ item.procedure_name }}</small>
        </span>
        <span>{{ item.worker_name || '未分配工人' }}</span>
        <span>数量 {{ item.quantity }}</span>
        <span>合格 {{ item.qualified_quantity }}</span>
        <ElTag :type="activePolicy.statusType(item)" size="small">{{ activePolicy.statusText(item) }}</ElTag>
        <span class="created-at">{{ item.created_at }}</span>
      </button>
    </div>
    <ElEmpty v-else-if="!loading" description="当前筛选下暂无关联工单" :image-size="60" />
  </section>

  <ElDrawer
    v-model="drawerVisible"
    title="工单详情"
    size="min(720px, 88%)"
    modal-class="production-workbench-drawer-overlay"
    class="production-workbench-drawer"
  >
    <template v-if="selectedWorkOrder">
      <header class="drawer-heading">
        <div>
          <p>{{ selectedWorkOrder.is_temporary ? '临时工单' : '工单' }}</p>
          <h2>{{ selectedWorkOrder.work_order_no }}</h2>
          <p>{{ selectedWorkOrder.part_no }} · {{ selectedWorkOrder.part_name }} · {{ selectedWorkOrder.procedure_name }}</p>
        </div>
        <ElTag :type="activePolicy.statusType(selectedWorkOrder)">{{ activePolicy.statusText(selectedWorkOrder) }}</ElTag>
      </header>
      <dl class="detail-grid">
        <div><dt>执行工人</dt><dd>{{ selectedWorkOrder.worker_name || '未分配' }}</dd></div>
        <div><dt>创建人</dt><dd>{{ selectedWorkOrder.created_by }}</dd></div>
        <div><dt>创建时间</dt><dd>{{ selectedWorkOrder.created_at }}</dd></div>
        <div><dt>工单数量</dt><dd>{{ selectedWorkOrder.quantity }}</dd></div>
        <div v-for="metric in activePolicy.metrics(selectedWorkOrder)" :key="metric.label">
          <dt>{{ metric.label }}</dt><dd>{{ metric.value }}</dd>
        </div>
      </dl>
      <p v-if="selectedWorkOrder.remark" class="remark">备注：{{ selectedWorkOrder.remark }}</p>

      <section v-if="selectedWorkOrder.input_materials.length" class="input-records">
        <h3>实际投入</h3>
        <div class="input-record-list">
          <article v-for="(material, index) in selectedWorkOrder.input_materials" :key="`${material.production_item_id}:${index}`">
            <strong>{{ material.item_code }} · {{ material.item_name }}</strong>
            <span>投入 {{ material.quantity }}</span>
            <span>{{ material.source_completion }}</span>
            <span>{{ material.source_work_order_no || '初始来源' }}</span>
          </article>
        </div>
      </section>

      <section v-if="selectedWorkOrder.batches.length" class="qc-records">
        <h3>质检记录</h3>
        <article v-for="(batch, index) in selectedWorkOrder.batches" :key="batch.id">
          <header>
            <strong>
              第 {{ index + 1 }} 批 ·
              {{ batch.rework_source_batch_id ? `第 ${batchSequence(selectedWorkOrder, batch.rework_source_batch_id)} 批返工复检` : '首次送检' }}
            </strong>
            <span>{{ qcResultText(batch) }}</span>
          </header>
          <p>送检 {{ batch.submitted_quantity }} · 合格 {{ batch.qualified_quantity || 0 }} · 返工 {{ batch.rework_quantity || 0 }} · 报废 {{ batch.scrap_quantity || 0 }} · 遗失 {{ batch.lost_quantity || 0 }}</p>
          <p v-if="batch.recorded_at">{{ batch.recorded_at }} · {{ batch.qc_worker_name }}</p>
          <p v-if="batch.defect_reason">不良原因：{{ batch.defect_reason }}</p>
          <ElButton
            v-if="activePolicy.showReworkQc(selectedWorkOrder, batch)"
            type="warning"
            plain
            size="small"
            @click="emit('resubmitQc', selectedWorkOrder, batch)"
          >返工送检</ElButton>
        </article>
      </section>

      <footer class="drawer-actions">
        <div>
          <ElButton
            v-if="activePolicy.showInitialQc(selectedWorkOrder)"
            type="warning"
            @click="emit('submitQc', selectedWorkOrder)"
          >送检</ElButton>
          <ElButton
            v-if="activePolicy.showDirectResult(selectedWorkOrder)"
            type="success"
            @click="emit('submitDirectResult', selectedWorkOrder)"
          >确认合格</ElButton>
        </div>
        <div>
          <ElButton @click="openPrint(selectedWorkOrder)">打印</ElButton>
          <ElButton
            v-if="activePolicy.showUndo(selectedWorkOrder)"
            type="danger"
            plain
            @click="emit('undo', selectedWorkOrder)"
          >{{ selectedWorkOrder.undo_operation?.operation_label }}</ElButton>
          <ElButton
            v-if="activePolicy.showCancel(selectedWorkOrder)"
            @click="emit('cancel', selectedWorkOrder)"
          >取消工单</ElButton>
        </div>
      </footer>
    </template>
  </ElDrawer>

  <PolishWorkOrderPrintDialog
    v-if="specialPrinting"
    v-model="printVisible"
    :item="printItem"
  />
  <WorkOrderPrintDialog v-else v-model="printVisible" :item="printItem" />
</template>

<style scoped>
.work-orders-section { min-height: 180px; padding: 14px 16px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); }
.work-orders-section > header { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
h3 { margin: 0; font-size: 15px; }
.work-orders-section > header span { color: var(--el-text-color-secondary); font-size: 12px; }
.compact-work-orders { display: grid; gap: 7px; margin-top: 10px; }
.compact-work-orders > button { display: grid; grid-template-columns: minmax(190px, 1.5fr) minmax(100px, .8fr) repeat(2, minmax(72px, .5fr)) auto minmax(130px, .8fr); gap: 10px; align-items: center; width: 100%; padding: 10px 11px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-sm); color: inherit; background: var(--md-surface-container-low); cursor: pointer; text-align: left; }
.compact-work-orders > button:hover { border-color: var(--md-primary); background: var(--md-primary-container); }
.compact-work-orders span { min-width: 0; font-size: 12px; }
.order-name { display: grid; gap: 2px; }
.order-name small, .created-at { color: var(--el-text-color-secondary); }
.drawer-heading { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; padding-bottom: 16px; border-bottom: 1px solid var(--erp-border); }
.drawer-heading h2, .drawer-heading p { margin: 0; }
.drawer-heading h2 { margin: 4px 0; font-size: 20px; }
.drawer-heading p { color: var(--el-text-color-secondary); font-size: 13px; }
.detail-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 16px 0 0; }
.detail-grid div { padding: 10px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-low); }
dt { color: var(--el-text-color-secondary); font-size: 12px; }
dd { margin: 5px 0 0; font-weight: 650; overflow-wrap: anywhere; }
.remark { padding: 10px 12px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-low); white-space: pre-wrap; }
.input-records { margin-top: 18px; }
.input-record-list { display: grid; gap: 7px; margin-top: 8px; }
.input-record-list article { display: grid; grid-template-columns: minmax(180px, 1.4fr) repeat(3, minmax(90px, .7fr)); gap: 10px; padding: 10px 12px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-low); }
.input-record-list span { color: var(--el-text-color-secondary); font-size: 12px; }
.qc-records { margin-top: 18px; }
.qc-records > article { margin-top: 8px; padding: 11px 12px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-low); }
.qc-records article header { display: flex; justify-content: space-between; gap: 10px; }
.qc-records article header span, .qc-records article p { color: var(--el-text-color-secondary); font-size: 12px; }
.qc-records article p { margin: 6px 0 0; }
.qc-records article :deep(.el-button) { margin-top: 8px; }
.drawer-actions { display: flex; justify-content: space-between; gap: 12px; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--erp-border); }
.drawer-actions > div { display: flex; flex-wrap: wrap; gap: 8px; }
.drawer-actions :deep(.el-button) { margin: 0; }
:global(.el-overlay.is-drawer.production-workbench-drawer-overlay) { background-color: transparent !important; }
@media (max-width: 900px) {
  .compact-work-orders > button { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .input-record-list article { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 600px) {
  .compact-work-orders > button, .detail-grid, .input-record-list article { grid-template-columns: 1fr; }
  .drawer-actions { flex-direction: column; }
}
</style>
