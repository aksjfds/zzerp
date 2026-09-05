<script setup lang="ts">
import { computed, ref } from 'vue'
import type {
  SupplierProcessingQcTask,
  WorkOrderBatch,
} from '../domain/types'
import type { WorkOrderRecordView } from '../domain/workOrderRecord'
import WorkOrderRecordCard from './WorkOrderRecordCard.vue'

const props = defineProps<{
  modelValue: boolean
  task?: SupplierProcessingQcTask
  undoingBatchId?: number | null
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  undoInspection: [batch: WorkOrderBatch]
  undoRelease: [batch: WorkOrderBatch]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const drawerRef = ref<{ handleClose: () => void } | null>(null)
const record = computed<WorkOrderRecordView | null>(() => {
  const task = props.task
  if (!task) return null
  return {
    id: task.work_order_id,
    work_order_no: task.work_order_no,
    work_order_type: 'supplier_processing',
    is_temporary: false,
    workshop_name: '委外加工',
    procedure_name: task.supplier_process_name,
    worker_name: task.supplier_name,
    quantity: task.task_quantity,
    processed_quantity: task.inspected_quantity,
    submitted_quantity: task.inspected_quantity,
    pending_qc_quantity: task.pending_destination_quantity,
    completed_quantity: task.released_quantity,
    rework_quantity: task.rework_quantity,
    scrap_quantity: task.scrap_quantity,
    lost_quantity: task.lost_quantity,
    status: task.status,
    created_at: task.created_at,
    closed_at: null,
    work_order: { batches: task.batches },
  }
})

function closeByContextMenu() {
  drawerRef.value?.handleClose()
}
</script>

<template>
  <ElDrawer
    ref="drawerRef"
    v-model="visible"
    title="委外工单和质检记录"
    size="76%"
    destroy-on-close
    modal-class="production-progress-overlay"
    class="production-progress-drawer"
    @contextmenu.prevent="closeByContextMenu"
  >
    <WorkOrderRecordCard v-if="record && task" :record="record">
      <template #metrics>
        <dl class="supplier-metrics">
          <div><dt>任务数</dt><dd>{{ task.task_quantity }}</dd></div>
          <div><dt>累计质检</dt><dd>{{ task.inspected_quantity }}</dd></div>
          <div><dt>累计合格</dt><dd class="success">{{ task.qualified_quantity }}</dd></div>
          <div><dt>累计返工</dt><dd>{{ task.rework_quantity }}</dd></div>
          <div><dt>累计报废</dt><dd :class="{ danger: task.scrap_quantity > 0 }">{{ task.scrap_quantity }}</dd></div>
          <div><dt>累计遗失</dt><dd :class="{ danger: task.lost_quantity > 0 }">{{ task.lost_quantity }}</dd></div>
          <div><dt>剩余待合格</dt><dd>{{ task.remaining_qualified_quantity }}</dd></div>
          <div><dt>待放行</dt><dd>{{ task.pending_destination_quantity }}</dd></div>
          <div><dt>已放行</dt><dd>{{ task.released_quantity }}</dd></div>
        </dl>
        <p v-if="task.remark" class="task-remark">备注：{{ task.remark }}</p>
      </template>
      <template #batchActions="{ batch }">
        <footer class="batch-actions">
          <ElButton
            v-if="task.status === 'open' && !batch.qualified_destination"
            type="danger"
            plain
            size="small"
            :loading="undoingBatchId === batch.id"
            :disabled="undoingBatchId !== null && undoingBatchId !== batch.id"
            @click="emit('undoInspection', batch)"
          >撤回质检</ElButton>
          <ElButton
            v-if="batch.qualified_destination"
            type="danger"
            plain
            size="small"
            :loading="undoingBatchId === batch.id"
            :disabled="undoingBatchId !== null && undoingBatchId !== batch.id"
            @click="emit('undoRelease', batch)"
          >撤回放行</ElButton>
        </footer>
      </template>
    </WorkOrderRecordCard>
    <ElEmpty v-else description="工单记录未加载" />
  </ElDrawer>
</template>

<style scoped>
:global(.el-overlay.is-drawer.production-progress-overlay) {
  --erp-drawer-transition-duration: 300ms;
  background-color: transparent !important;
}

.supplier-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
  margin: 14px 0 0;
}

.supplier-metrics div {
  min-width: 0;
  padding: 9px 10px;
  border-radius: var(--erp-radius-sm);
  background: var(--md-surface-container-low);
}

.supplier-metrics dt {
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

.supplier-metrics dd {
  margin: 4px 0 0;
  font-weight: 700;
}

.task-remark {
  margin: 10px 0 0;
  color: var(--md-on-surface-variant);
  font-size: 13px;
}

.batch-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.batch-actions :deep(.el-button) {
  margin: 0;
}

.success { color: #22c55e; }
.danger { color: var(--el-color-danger); font-weight: 700; }

@media (max-width: 900px) {
  .supplier-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .supplier-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
