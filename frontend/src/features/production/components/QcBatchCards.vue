<script setup lang="ts">
import type { PendingQcBatch } from '../domain/types'
defineProps<{ items: PendingQcBatch[]; loading: boolean }>()
defineEmits<{ inspect: [batch: PendingQcBatch] }>()
</script>
<template>
  <div v-loading="loading" class="qc-list">
    <article v-for="batch in items" :key="batch.id" class="qc-card">
      <strong>工单 {{ batch.work_order_no }}</strong>
      <p>{{ batch.part_no }} - {{ batch.part_name }}</p>
      <p>工艺：{{ batch.procedure_name }} · </p>
      <template v-if="batch.recorded_at">
        <p>送检：{{ batch.submitted_quantity }} · 合格 {{ batch.qualified_quantity || 0 }} · 返工 {{ batch.rework_quantity || 0
          }} · 报废 {{ batch.scrap_quantity || 0 }} · 遗失 {{ batch.lost_quantity || 0 }}</p>
        <p>{{ batch.qc_worker_name }}</p>
        <p>{{ batch.recorded_at }}</p>
        <p v-if="batch.defect_reason">不良原因：{{ batch.defect_reason }}</p>
      </template>
      <ElButton v-else type="primary" size="small" @click="$emit('inspect', batch)">录入 QC 结果</ElButton>
    </article>
    <ElEmpty v-if="!items.length" description="所选配件暂无 QC 记录" :image-size="64" />
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
</style>
