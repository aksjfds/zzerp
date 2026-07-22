<script setup lang="ts">
import type { PendingQcBatch } from '../domain/types'
defineProps<{
  items: PendingQcBatch[]
  loading: boolean
  submitting?: boolean
  history?: boolean
}>()
defineEmits<{
  inspect: [batch: PendingQcBatch]
  dispatch: [batch: PendingQcBatch]
}>()

function itemName(batch: PendingQcBatch) {
  return batch.part_no === batch.part_name
    ? batch.part_name
    : `${batch.part_no} - ${batch.part_name}`
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
      </template>
      <ElButton v-else-if="!history" type="primary" size="small" @click="$emit('inspect', batch)">录入 QC 结果</ElButton>
      <div v-if="batch.dispatchable_quantity > 0" class="dispatch-row">
        <span>合格待出货 {{ batch.dispatchable_quantity }} 件 → {{ batch.target_node_label }}</span>
        <ElButton
          type="success"
          size="small"
          :loading="submitting"
          @click="$emit('dispatch', batch)"
        >出货</ElButton>
      </div>
    </article>
    <ElEmpty
      v-if="!loading && !items.length"
      :description="history ? '暂无历史质检记录' : '暂无待检或待出货批次'"
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
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #f8fafc;
}

.qc-card p {
  margin: 7px 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.dispatch-row { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-top: 10px; }
</style>
