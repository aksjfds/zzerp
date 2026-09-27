<script setup lang="ts">
import type {
  QcDestination,
  QcInspectionBatchRow,
} from '../domain/types'

defineProps<{
  items: QcInspectionBatchRow[]
  loading: boolean
  decidingBatchId?: number | null
  undoingBatchId?: number | null
}>()
const emit = defineEmits<{
  inspect: [batch: QcInspectionBatchRow]
  view: [batch: QcInspectionBatchRow]
  decide: [batch: QcInspectionBatchRow, destination: QcDestination]
  undoInspection: [batch: QcInspectionBatchRow]
  undoDestination: [batch: QcInspectionBatchRow]
}>()

const destinationLabels: Record<QcDestination, string> = {
  return: '送回',
  release: '放行',
  inventory: '存入仓库',
}

function batchStatus(batch: QcInspectionBatchRow) {
  if (!batch.recorded_at) return { label: '待质检', type: 'warning' as const }
  if (batch.qualified_quantity && !batch.qualified_destination) {
    return { label: '待决定去向', type: 'primary' as const }
  }
  if (batch.qualified_destination) {
    return { label: destinationLabels[batch.qualified_destination], type: 'success' as const }
  }
  return { label: '质检完成', type: 'success' as const }
}

function destinationLabel(destination: QcDestination) {
  return destinationLabels[destination]
}
</script>

<template>
  <ElTable
    v-table-column-widths="'production.qc-inspection-batches'"
    v-loading="loading"
    :data="items"
    row-key="id"
    border
    stripe
    table-layout="auto"
    empty-text="暂无质检批次"
  >
    <ElTableColumn label="物料" min-width="190">
      <template #default="{ row }">
        <strong>
          <template v-if="row.part_no && row.part_no !== row.part_name">{{ row.part_no }} · </template>{{ row.part_name }}
        </strong>
      </template>
    </ElTableColumn>
    <ElTableColumn label="工单号" min-width="170">
      <template #default="{ row }">
        <strong>工单{{ row.work_order_no }}</strong>
        <div class="batch-context">订单 {{ row.customer_order_no }}</div>
      </template>
    </ElTableColumn>
    <ElTableColumn label="质检批次" min-width="110">
      <template #default="{ row }">
        第 {{ row.batch_sequence }} 批
        <div v-if="row.rework_source_batch_sequence" class="batch-context">第 {{ row.rework_source_batch_sequence }} 批返工</div>
      </template>
    </ElTableColumn>
    <ElTableColumn prop="submitted_quantity" label="送检数" min-width="85" align="right" />
    <ElTableColumn label="合格数" min-width="85" align="right">
      <template #default="{ row }">{{ row.qualified_quantity ?? '—' }}</template>
    </ElTableColumn>
    <ElTableColumn prop="work_order_name" label="工艺" min-width="120" />
    <ElTableColumn prop="worker_name" label="加工工人" min-width="110">
      <template #default="{ row }">{{ row.worker_name || '—' }}</template>
    </ElTableColumn>
    <ElTableColumn label="状态" min-width="110">
      <template #default="{ row }">
        <ElTag :type="batchStatus(row).type" effect="light" size="small">
          {{ batchStatus(row).label }}
        </ElTag>
      </template>
    </ElTableColumn>
    <ElTableColumn label="操作" min-width="300">
      <template #default="{ row }">
        <div class="batch-actions">
          <ElButton
            v-if="!row.recorded_at"
            type="primary"
            link
            @click="emit('inspect', row)"
          >录入</ElButton>
          <ElButton link @click="emit('view', row)">查看</ElButton>
          <ElButton
            v-for="destination in row.allowed_destinations"
            :key="destination"
            :type="destination === 'inventory' ? 'success' : 'primary'"
            link
            :loading="decidingBatchId === row.id"
            :disabled="decidingBatchId !== null && decidingBatchId !== row.id"
            @click="emit('decide', row, destination)"
          >{{ destinationLabel(destination) }}</ElButton>
          <ElButton
            v-if="row.can_undo_inspection"
            type="danger"
            link
            :loading="undoingBatchId === row.id"
            :disabled="undoingBatchId !== null && undoingBatchId !== row.id"
            @click="emit('undoInspection', row)"
          >撤回质检</ElButton>
          <ElButton
            v-if="row.qualified_destination"
            type="danger"
            link
            :loading="undoingBatchId === row.id"
            :disabled="undoingBatchId !== null && undoingBatchId !== row.id"
            @click="emit('undoDestination', row)"
          >撤回去向</ElButton>
        </div>
      </template>
    </ElTableColumn>
  </ElTable>
</template>

<style scoped>
.batch-context { color: var(--erp-text-secondary); font-size: 12px; }
.batch-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px 8px;
}

.batch-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
