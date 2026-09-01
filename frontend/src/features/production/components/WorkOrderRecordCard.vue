<script setup lang="ts">
import { computed } from 'vue'
import { workOrderStatusLabel } from '../domain/workOrderStatus'
import type { WorkOrderBatch } from '../domain/types'
import type { WorkOrderRecordView } from '../domain/workOrderRecord'

const props = withDefaults(defineProps<{
  record: WorkOrderRecordView
  batches?: WorkOrderBatch[]
  highlightedBatchIds?: number[]
  exceptionMode?: boolean
}>(), {
  batches: undefined,
  highlightedBatchIds: () => [],
  exceptionMode: false,
})

defineSlots<{
  contextTag?: () => unknown
  metrics?: () => unknown
  batchTag?: (props: { batch: WorkOrderBatch }) => unknown
  batchActions?: (props: { batch: WorkOrderBatch }) => unknown
  actions?: () => unknown
}>()

const displayedBatches = computed(() => props.batches || props.record.work_order.batches)
const highlightedBatchIds = computed(() => new Set(props.highlightedBatchIds))

function orderType() {
  if (props.record.is_temporary) return '临时工单'
  if (props.record.work_order_type === 'assembly') return '装配工单'
  return props.record.work_order_type === 'supplier_processing' ? '委外工单' : '生产工单'
}

function statusType(): 'warning' | 'success' | 'info' {
  if (props.record.status === 'open') return 'warning'
  return props.record.status === 'closed' ? 'success' : 'info'
}

function batchStatus(batch: WorkOrderBatch) {
  if (!batch.recorded_at) return { label: '待质检', type: 'warning' as const }
  if (batch.qualified_quantity && !batch.qualified_destination) {
    return { label: '待决定去向', type: 'warning' as const }
  }
  return { label: '已质检', type: 'success' as const }
}

function batchSequence(batchId: number) {
  const index = props.record.work_order.batches.findIndex(batch => batch.id === batchId)
  return index >= 0 ? index + 1 : '—'
}

const destinationLabels = {
  return: '返回当前车间',
  release: '放行下一节点',
  inventory: '存入仓库',
}
</script>

<template>
  <article class="work-order-card">
    <header class="work-order-heading">
      <div>
        <span>{{ orderType() }}</span>
        <h3>{{ record.work_order_no }}</h3>
      </div>
      <ElTag :type="statusType()" effect="light">
        {{ workOrderStatusLabel(record.status) }}
      </ElTag>
    </header>

    <slot name="contextTag" />

    <dl class="work-order-context">
      <div><dt>车间</dt><dd>{{ record.workshop_name }}</dd></div>
      <div><dt>工艺</dt><dd>{{ record.procedure_name }}</dd></div>
      <div><dt>工人 / 公司</dt><dd>{{ record.worker_name || '—' }}</dd></div>
    </dl>

    <slot name="metrics">
      <dl class="work-order-metrics">
        <div><dt>工单数</dt><dd>{{ record.quantity }}</dd></div>
        <div><dt>加工数</dt><dd>{{ record.processed_quantity }}</dd></div>
        <div><dt>送检数</dt><dd>{{ record.submitted_quantity }}</dd></div>
        <div><dt>待检数</dt><dd>{{ record.pending_qc_quantity }}</dd></div>
        <div><dt>完成数</dt><dd class="success">{{ record.completed_quantity }}</dd></div>
        <div><dt>返工数</dt><dd>{{ record.rework_quantity }}</dd></div>
        <div>
          <dt>异常数</dt>
          <dd :class="{ danger: record.scrap_quantity + record.lost_quantity > 0 }">
            {{ record.scrap_quantity + record.lost_quantity }}
          </dd>
        </div>
      </dl>
    </slot>

    <footer class="work-order-time">
      <span>创建：{{ record.created_at }}</span>
      <span>完成：{{ record.closed_at || '—' }}</span>
    </footer>

    <section v-if="displayedBatches.length" class="qc-batches">
      <header>
        <h4>QC 批次</h4>
        <span>{{ displayedBatches.length }} 批</span>
      </header>
      <div class="qc-batch-list">
        <article
          v-for="batch in displayedBatches"
          :key="batch.id"
          class="qc-batch"
          :class="{
            'is-related': highlightedBatchIds.has(batch.id),
            'is-exception': exceptionMode && highlightedBatchIds.has(batch.id),
          }"
        >
          <header>
            <strong>
              第 {{ batchSequence(batch.id) }} 批
              <template v-if="batch.rework_source_batch_id">
                · 第 {{ batchSequence(batch.rework_source_batch_id) }} 批返工复检
              </template>
            </strong>
            <ElTag :type="batchStatus(batch).type" size="small" effect="light">
              {{ batchStatus(batch).label }}
            </ElTag>
            <slot name="batchTag" :batch="batch" />
          </header>
          <dl class="qc-batch-metrics">
            <div><dt>送检</dt><dd>{{ batch.submitted_quantity }}</dd></div>
            <template v-if="batch.recorded_at">
              <div><dt>合格</dt><dd class="success">{{ batch.qualified_quantity || 0 }}</dd></div>
              <div><dt>返工</dt><dd>{{ batch.rework_quantity || 0 }}</dd></div>
              <div>
                <dt>报废</dt>
                <dd :class="{ danger: (batch.scrap_quantity || 0) > 0 }">
                  {{ batch.scrap_quantity || 0 }}
                </dd>
              </div>
              <div>
                <dt>遗失</dt>
                <dd :class="{ danger: (batch.lost_quantity || 0) > 0 }">
                  {{ batch.lost_quantity || 0 }}
                </dd>
              </div>
              <div v-if="batch.rework_pending_quantity">
                <dt>待返工</dt><dd>{{ batch.rework_pending_quantity }}</dd>
              </div>
            </template>
          </dl>
          <div v-if="batch.recorded_at" class="qc-batch-detail">
            <span>QC：{{ batch.qc_worker_name || '—' }}</span>
            <span>质检时间：{{ batch.recorded_at }}</span>
            <span v-if="batch.qualified_destination">
              去向：{{ destinationLabels[batch.qualified_destination] }}
              · {{ batch.destination_decided_by || '—' }}
              · {{ batch.destination_decided_at || '—' }}
            </span>
            <span v-else-if="batch.qualified_quantity">合格品尚未决定去向</span>
            <span v-if="batch.defect_reason" class="qc-defect">
              不良原因：{{ batch.defect_reason }}
            </span>
          </div>
          <slot name="batchActions" :batch="batch" />
        </article>
      </div>
    </section>

    <slot name="actions" />
  </article>
</template>

<style scoped>
.work-order-card { width: 100%; min-width: 0; box-sizing: border-box; padding: 16px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.work-order-heading, .qc-batches > header, .qc-batch > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.work-order-heading h3, .work-order-heading > div > span { margin: 0; }
.work-order-heading h3 { margin-top: 4px; font-size: 17px; overflow-wrap: anywhere; }
.work-order-heading > div > span, .qc-batches > header > span, .qc-batch-detail { color: var(--md-on-surface-variant); font-size: 12px; }
.work-order-context, .work-order-metrics { display: grid; margin: 14px 0 0; }
.work-order-context { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.work-order-context div, .work-order-metrics div { min-width: 0; padding: 9px 10px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-low); }
.work-order-metrics { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
.work-order-card dt { color: var(--md-on-surface-variant); font-size: 12px; }
.work-order-card dd { margin: 4px 0 0; font-weight: 700; overflow-wrap: anywhere; }
.work-order-time { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 16px; margin-top: 12px; color: var(--md-on-surface-variant); font-size: 12px; }
.qc-batches { margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--md-outline-variant); }
.qc-batches > header { align-items: center; }
.qc-batches h4 { margin: 0; font-size: 14px; }
.qc-batch-list { display: grid; gap: 8px; margin-top: 10px; }
.qc-batch { padding: 12px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-sm); background: var(--md-surface-container-low); }
.qc-batch.is-related { border-color: var(--el-color-primary-light-5); background: var(--el-color-primary-light-9); }
.qc-batch.is-exception { border-color: var(--el-color-danger-light-5); background: var(--el-color-danger-light-9); }
.qc-batch-metrics { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 6px; margin: 10px 0 0; }
.qc-batch-metrics div { padding: 7px 8px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-lowest); }
.qc-batch-detail { display: flex; flex-wrap: wrap; gap: 5px 18px; margin-top: 10px; }
.qc-defect { flex-basis: 100%; color: var(--el-color-danger); }
.success { color: #22c55e; }
.danger { color: var(--el-color-danger); font-weight: 700; }
@media (max-width: 680px) {
  .work-order-context { grid-template-columns: 1fr; }
  .work-order-metrics, .qc-batch-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
