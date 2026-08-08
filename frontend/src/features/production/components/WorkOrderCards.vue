<script setup lang="ts">
import { computed, ref } from 'vue'
import type { WorkOrder, WorkOrderBatch } from '../domain/types'
import type { WorkOrderMode } from '../domain/workOrderCardPolicy'
import { assemblyWorkOrderCardPolicy } from '../domain/assemblyWorkOrderCardPolicy'
import { productionWorkOrderCardPolicy } from '../domain/productionWorkOrderCardPolicy'
import { purchaseWorkOrderCardPolicy } from '../domain/purchaseWorkOrderCardPolicy'
import PolishWorkOrderPrintDialog from './PolishWorkOrderPrintDialog.vue'
import WorkOrderPrintDialog from './WorkOrderPrintDialog.vue'

const props = withDefaults(defineProps<{
  items: WorkOrder[]
  loading: boolean
  mode?: WorkOrderMode
  specialPrinting?: boolean
}>(), { mode: 'production' })
const emit = defineEmits<{
  submit: [item: WorkOrder]
  submitQc: [item: WorkOrder]
  submitDirectResult: [item: WorkOrder]
  resubmitQc: [item: WorkOrder, batch: WorkOrderBatch]
  cancel: [item: WorkOrder]
  undo: [item: WorkOrder]
}>()

const policies = {
  production: productionWorkOrderCardPolicy,
  purchase: purchaseWorkOrderCardPolicy,
  assembly: assemblyWorkOrderCardPolicy,
}
const policy = computed(() => policies[props.mode])
const printVisible = ref(false)
const printItem = ref<WorkOrder>()

function openPrint(item: WorkOrder) {
  printItem.value = item
  printVisible.value = true
}

function batchSequence(item: WorkOrder, batchId: number) {
  const index = item.batches.findIndex(batch => batch.id === batchId)
  return index >= 0 ? index + 1 : '—'
}

function qcResultText(batch: WorkOrderBatch) {
  const hasRework = Boolean(batch.rework_quantity)
  const hasLoss = Boolean(batch.scrap_quantity || batch.lost_quantity)
  if (hasRework && hasLoss) return '混合异常'
  if (hasLoss) return '含报废/遗失'
  if (hasRework) return '含返工'
  if (batch.qualified_quantity === batch.submitted_quantity) return '全部合格'
  return '已检验'
}

function qcResultType(batch: WorkOrderBatch): 'success' | 'info' | 'warning' | 'danger' {
  if (batch.scrap_quantity || batch.lost_quantity) return 'danger'
  if (batch.rework_quantity) return 'warning'
  return batch.qualified_quantity === batch.submitted_quantity ? 'success' : 'info'
}

</script>

<template>
  <div v-loading="loading" class="work-order-list">
    <article v-for="item in items" :key="item.id" class="work-order-card">
      <div class="heading">
        <div><strong>工单 {{ item.work_order_no }}</strong><span>{{ item.work_order_name }}</span></div>
        <ElTag :type="policy.statusType(item)">{{ policy.statusText(item) }}</ElTag>
      </div>
      <div class="meta">
        <span>{{ item.part_no === item.part_name ? item.part_name : `${item.part_no} - ${item.part_name}` }}</span>
        <span>执行工人：{{ item.worker_name || '未分配' }}</span>
        <span>创建：{{ item.created_at }}</span>
      </div>
      <p v-if="item.remark" class="remark">备注：{{ item.remark }}</p>
      <dl class="metrics" :class="policy.metricsClass">
        <div v-for="metric in policy.metrics(item)" :key="metric.label">
          <dt>{{ metric.label }}</dt><dd>{{ metric.value }}</dd>
        </div>
      </dl>
      <div v-if="policy.showBatches && item.batches.length" class="batches">
        <h4>{{ policy.batchTitle }}</h4>
        <div v-for="(batch, batchIndex) in item.batches" :key="batch.id" class="batch-row">
          <div class="batch-heading">
            <strong>
              第 {{ batchIndex + 1 }} 批 ·
              {{ batch.rework_source_batch_id ? `第 ${batchSequence(item, batch.rework_source_batch_id)} 批返工复检` : '首次送检' }}
              {{ batch.submitted_quantity }}
            </strong>
            <ElTag v-if="!batch.recorded_at" type="warning" size="small">等待 QC</ElTag>
            <div v-else class="batch-result">
              <ElTag :type="qcResultType(batch)" size="small">{{ qcResultText(batch) }}</ElTag>
              <span>{{ batch.recorded_at }} · {{ batch.qc_worker_name }}</span>
            </div>
          </div>
          <p v-if="batch.recorded_at">
            合格 {{ batch.qualified_quantity || 0 }} · 返工 {{ batch.rework_quantity || 0 }} ·
            报废 {{ batch.scrap_quantity || 0 }} · 遗失 {{ batch.lost_quantity || 0 }}
          </p>
          <p v-if="batch.defect_reason">不良原因：{{ batch.defect_reason }}</p>
          <div v-if="policy.showReworkQc(item, batch)" class="batch-rework">
            <span>返工待加工 {{ batch.rework_pending_quantity }}</span>
            <ElButton
              type="warning"
              plain
              size="small"
              :disabled="item.status !== 'open'"
              @click="emit('resubmitQc', item, batch)"
            >返工送检</ElButton>
          </div>
          <p v-else-if="policy.trackRework && batch.recorded_at && batch.rework_quantity">
            返工已全部重新送检
          </p>
        </div>
      </div>
      <div class="work-order-actions">
        <div class="primary-actions">
          <ElButton
            v-if="policy.showComplete(item)"
            type="primary"
            size="small"
            :disabled="policy.disableComplete(item)"
            @click="emit('submit', item)"
          >{{ policy.completeLabel(item) }}</ElButton>
          <ElButton
            v-if="policy.showInitialQc(item)"
            type="warning"
            size="small"
            @click="emit('submitQc', item)"
          >送检（{{ item.ready_for_qc_quantity }}）</ElButton>
          <ElButton
            v-if="policy.showDirectResult(item)"
            type="success"
            size="small"
            @click="emit('submitDirectResult', item)"
          >{{ mode === 'assembly' ? '填写装配结果' : '填写加工结果' }}（{{ item.ready_for_qc_quantity }}）</ElButton>
        </div>
        <div class="utility-actions">
          <ElButton size="small" plain @click="openPrint(item)">打印工单</ElButton>
          <ElButton
            v-if="item.undo_operation"
            type="danger"
            plain
            size="small"
            @click="emit('undo', item)"
          >{{ item.undo_operation.operation_label }}</ElButton>
          <ElButton
            v-if="item.status === 'open' && item.processed_quantity === 0"
            size="small"
            @click="emit('cancel', item)"
          >取消工单</ElButton>
        </div>
      </div>
    </article>
    <ElEmpty v-if="!loading && !items.length" description="所选配件暂无工单" :image-size="64" />
    <PolishWorkOrderPrintDialog
      v-if="specialPrinting"
      v-model="printVisible"
      :item="printItem"
    />
    <WorkOrderPrintDialog v-else v-model="printVisible" :item="printItem" />
  </div>
</template>

<style scoped>
.work-order-list { display: grid; gap: 14px; min-height: 160px; }
.work-order-card { padding: 16px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
.heading { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.heading div { display: grid; gap: 4px; }
.heading span, .meta { color: var(--el-text-color-secondary); font-size: 13px; }
.meta { display: flex; flex-wrap: wrap; gap: 8px 20px; margin-top: 12px; }
.remark { margin: 10px 0 0; padding: 9px 11px; border-radius: var(--erp-radius-sm); color: var(--md-on-surface-variant); background: var(--md-surface-container-lowest); font-size: 13px; white-space: pre-wrap; }
.metrics { display: grid; grid-template-columns: repeat(6, minmax(80px, 1fr)); gap: 8px; margin: 14px 0 0; }
.metrics div { padding: 10px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-lowest); }
.metrics dt { color: var(--el-text-color-secondary); font-size: 12px; }
.metrics dd { margin: 5px 0 0; font-size: 17px; font-weight: 700; }
.purchase-metrics, .assembly-metrics { grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); }
.batches { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--erp-border); }
.batches h4 { margin: 0 0 8px; font-size: 13px; }
.batch-row { padding: 9px 10px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-lowest); font-size: 12px; }
.batch-row + .batch-row { margin-top: 7px; }
.batch-heading { display: flex; justify-content: space-between; gap: 10px; color: var(--el-text-color-secondary); }
.batch-heading strong { color: var(--erp-text); }
.batch-result { display: flex; flex-wrap: wrap; justify-content: flex-end; align-items: center; gap: 8px; }
.batch-row p { margin: 6px 0 0; color: var(--el-text-color-secondary); }
.batch-rework { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 8px; color: var(--el-color-warning); }
.work-order-actions { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 12px 20px; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--erp-border); }
.primary-actions, .utility-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.utility-actions { justify-content: flex-end; }
.work-order-actions :deep(.el-button) { margin: 0; }
@media (max-width: 1150px) { .metrics { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 620px) {
  .heading, .batch-heading { align-items: flex-start; flex-direction: column; }
  .batch-result { justify-content: flex-start; }
  .metrics, .purchase-metrics, .assembly-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .work-order-actions { grid-template-columns: 1fr; width: 100%; }
  .primary-actions, .utility-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); width: 100%; }
  .work-order-actions :deep(.el-button) { width: 100%; }
}
@media (max-width: 420px) {
  .primary-actions, .utility-actions { grid-template-columns: 1fr; }
}
</style>
