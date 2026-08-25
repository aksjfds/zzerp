<script setup lang="ts">
import type { PendingQcBatch } from '../domain/types'
defineProps<{
  items: PendingQcBatch[]
  loading: boolean
  history?: boolean
  decidingBatchId?: number | null
}>()
defineEmits<{
  inspect: [batch: PendingQcBatch]
  decide: [batch: PendingQcBatch, destination: PendingQcBatch['allowed_destinations'][number]]
}>()

function itemName(batch: PendingQcBatch) {
  return batch.part_no === batch.part_name
    ? batch.part_name
    : `${batch.part_no} - ${batch.part_name}`
}

const destinationLabels = {
  return: '返回当前车间',
  release: '放行下一节点',
  inventory: '存入仓库',
}
</script>
<template>
  <div v-loading="loading" class="qc-list">
    <article v-for="batch in items" :key="batch.id" class="qc-card">
      <strong>工单 {{ batch.work_order_no }}</strong>
      <p>{{ itemName(batch) }}</p>
      <p>订单：{{ batch.customer_order_no }}</p>
      <p>工单内容：{{ batch.work_order_name }}</p>
      <template v-if="batch.recorded_at">
        <p>送检：{{ batch.submitted_quantity }} · 合格 {{ batch.qualified_quantity || 0 }} · 返工 {{ batch.rework_quantity || 0
          }} · 报废 {{ batch.scrap_quantity || 0 }} · 遗失 {{ batch.lost_quantity || 0 }}</p>
        <p>{{ batch.qc_worker_name }}</p>
        <p>{{ batch.recorded_at }}</p>
        <p v-if="batch.defect_reason">不良原因：{{ batch.defect_reason }}</p>
        <p v-if="batch.qualified_destination">
          合格品去向：{{ destinationLabels[batch.qualified_destination] }}
          · {{ batch.destination_decided_by }} · {{ batch.destination_decided_at }}
        </p>
        <p v-else-if="batch.qualified_quantity">QC 结果已保存，合格品待决定去向</p>
      </template>
      <ElButton
        v-if="!history && !batch.recorded_at"
        type="primary"
        size="small"
        @click="$emit('inspect', batch)"
      >录入 QC 结果</ElButton>
      <div
        v-if="!history && batch.recorded_at && batch.qualified_quantity && !batch.qualified_destination"
        class="dispatch-row"
      >
        <span>请选择合格品去向</span>
        <div>
          <ElButton
            v-for="destination in batch.allowed_destinations"
            :key="destination"
            :type="destination === 'inventory' ? 'success' : 'primary'"
            plain
            size="small"
            :loading="decidingBatchId === batch.id"
            :disabled="decidingBatchId !== null && decidingBatchId !== batch.id"
            @click="$emit('decide', batch, destination)"
          >{{ destinationLabels[destination] }}</ElButton>
        </div>
      </div>
    </article>
    <ElEmpty
      v-if="!loading && !items.length"
      :description="history ? '暂无历史质检记录' : '暂无待处理批次'"
      :image-size="64"
    />
  </div>
</template>
<style scoped>
.qc-list {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.qc-card {
  padding: 14px;
  border: 1px solid transparent;
  border-radius: var(--erp-radius);
  background: var(--md-surface-container-low);
}

.qc-card p {
  margin: 7px 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.dispatch-row { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-top: 10px; }
@media (max-width: 560px) {
  .dispatch-row { align-items: stretch; flex-direction: column; }
  .dispatch-row :deep(.el-button) { width: 100%; }
}
</style>
