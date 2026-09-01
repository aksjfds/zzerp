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
        <strong>{{ row.part_no }} {{ row.part_name }}</strong>
      </template>
    </ElTableColumn>
    <ElTableColumn label="工单号" min-width="170">
      <template #default="{ row }">
        <strong>工单{{ row.work_order_no }}</strong>
      </template>
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
          >{{ destinationLabels[destination] }}</ElButton>
          <ElButton
            v-if="row.can_undo_inspection"
            type="danger"
            link
            :loading="undoingBatchId === row.id"
            :disabled="undoingBatchId !== null && undoingBatchId !== row.id"
            @click="emit('undoInspection', row)"
          >撤回质检</ElButton>
        </div>
      </template>
    </ElTableColumn>
  </ElTable>
</template>

<style scoped>
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
