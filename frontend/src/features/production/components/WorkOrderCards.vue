<script setup lang="ts">
import type { WorkOrder } from '../domain/types'

const props = withDefaults(defineProps<{
  items: WorkOrder[]
  loading: boolean
  mode?: 'production' | 'purchase' | 'assembly'
}>(), { mode: 'production' })
const emit = defineEmits<{
  submit: [item: WorkOrder]
  submitQc: [item: WorkOrder]
  cancel: [item: WorkOrder]
}>()

function statusText(item: WorkOrder) {
  if (item.status === 'cancelled') return '已取消'
  if (props.mode !== 'assembly' && item.pending_qc_quantity) return `${item.work_order_name}质检中`
  if (item.status === 'closed') return props.mode === 'purchase' ? '已全部到货' : '已结单'
  if (props.mode === 'purchase') return '采购 / 到货中'
  return props.mode === 'assembly' ? `${item.work_order_name}装配中` : `${item.work_order_name}加工中`
}

function statusType(item: WorkOrder): 'primary' | 'success' | 'info' | 'warning' {
  if (item.status === 'cancelled') return 'info'
  if (props.mode !== 'assembly' && item.pending_qc_quantity) return 'warning'
  return item.status === 'closed' ? 'success' : 'primary'
}
</script>

<template>
  <div v-loading="loading" class="work-order-list">
    <article v-for="item in items" :key="item.id" class="work-order-card">
      <div class="heading">
        <div><strong>工单 {{ item.work_order_no }}</strong><span>{{ item.work_order_name }}</span></div>
        <ElTag :type="statusType(item)">{{ statusText(item) }}</ElTag>
      </div>
      <div class="meta">
        <span>{{ item.part_no === item.part_name ? item.part_name : `${item.part_no} - ${item.part_name}` }}</span>
        <span>执行工人：{{ item.worker_name || '未分配' }}</span>
        <span>创建：{{ item.created_at }}</span>
      </div>
      <dl v-if="props.mode === 'purchase'" class="metrics purchase-metrics">
        <div><dt>外购数量</dt><dd>{{ item.quantity }}</dd></div>
        <div><dt>已登记</dt><dd>{{ item.submitted_quantity }}</dd></div>
        <div><dt>质检中</dt><dd>{{ item.pending_qc_quantity }}</dd></div>
        <div><dt>已合格入库</dt><dd>{{ item.qualified_quantity }}</dd></div>
        <div><dt>待到货</dt><dd>{{ item.processing_quantity }}</dd></div>
      </dl>
      <dl v-else-if="props.mode === 'assembly'" class="metrics assembly-metrics">
        <div><dt>装配数量</dt><dd>{{ item.quantity }}</dd></div>
        <div><dt>装配中</dt><dd>{{ item.processing_quantity }}</dd></div>
        <div><dt>已完成</dt><dd>{{ item.submitted_quantity }}</dd></div>
        <div><dt>报废 / 遗失</dt><dd>{{ item.scrap_quantity }} / {{ item.lost_quantity }}</dd></div>
      </dl>
      <dl v-else class="metrics">
        <div><dt>领料数</dt><dd>{{ item.quantity }}</dd></div>
        <div><dt>加工中</dt><dd>{{ item.processing_quantity }}</dd></div>
        <div><dt>质检中</dt><dd>{{ item.pending_qc_quantity }}</dd></div>
        <div><dt>累计合格</dt><dd>{{ item.qualified_quantity }}</dd></div>
        <div><dt>累计返工</dt><dd>{{ item.rework_quantity }}</dd></div>
        <div><dt>报废 / 遗失</dt><dd>{{ item.scrap_quantity }} / {{ item.lost_quantity }}</dd></div>
      </dl>
      <div v-if="props.mode !== 'assembly' && item.batches.length" class="batches">
        <h4>{{ props.mode === 'purchase' ? '到货与 QC 记录' : '送检与 QC 记录' }}</h4>
        <div v-for="batch in item.batches" :key="batch.id" class="batch-row">
          <div class="batch-heading">
            <strong>第 {{ batch.id }} 批 · 送检 {{ batch.submitted_quantity }}</strong>
            <ElTag v-if="!batch.recorded_at" type="warning" size="small">等待 QC</ElTag>
            <span v-else>{{ batch.recorded_at }} · {{ batch.qc_worker_name }}</span>
          </div>
          <p v-if="batch.recorded_at">
            合格 {{ batch.qualified_quantity || 0 }} · 返工 {{ batch.rework_quantity || 0 }} ·
            报废 {{ batch.scrap_quantity || 0 }} · 遗失 {{ batch.lost_quantity || 0 }}
          </p>
          <p v-if="batch.defect_reason">不良原因：{{ batch.defect_reason }}</p>
        </div>
      </div>
      <div class="work-order-actions">
        <ElButton
          v-if="item.status === 'open' && item.processing_quantity > 0"
          type="primary"
          size="small"
          @click="emit('submit', item)"
        >{{ props.mode === 'purchase' ? '登记到货 / 送检' : props.mode === 'assembly' ? '完成装配' : '完成细分' }}</ElButton>
        <ElButton
          v-if="props.mode === 'production' && item.status === 'open' && item.processing_quantity > 0"
          type="warning"
          plain
          size="small"
          @click="emit('submitQc', item)"
        >送检</ElButton>
        <ElButton
          v-if="item.status === 'open' && item.submitted_quantity === 0"
          size="small"
          @click="emit('cancel', item)"
        >取消工单</ElButton>
      </div>
    </article>
    <ElEmpty v-if="!loading && !items.length" description="所选配件暂无工单" :image-size="64" />
  </div>
</template>

<style scoped>
.work-order-list { display: grid; gap: 14px; min-height: 160px; }
.work-order-card { padding: 16px; border: 1px solid var(--erp-border); border-radius: 8px; background: #f8fafc; }
.heading { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.heading div { display: grid; gap: 4px; }
.heading span, .meta { color: var(--el-text-color-secondary); font-size: 13px; }
.meta { display: flex; flex-wrap: wrap; gap: 8px 20px; margin-top: 12px; }
.metrics { display: grid; grid-template-columns: repeat(6, minmax(80px, 1fr)); gap: 8px; margin: 14px 0 0; }
.metrics div { padding: 10px; border-radius: 6px; background: #fff; }
.metrics dt { color: var(--el-text-color-secondary); font-size: 12px; }
.metrics dd { margin: 5px 0 0; font-size: 17px; font-weight: 700; }
.purchase-metrics { grid-template-columns: repeat(5, minmax(90px, 1fr)); }
.assembly-metrics { grid-template-columns: repeat(4, minmax(100px, 1fr)); }
.batches { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--erp-border); }
.batches h4 { margin: 0 0 8px; font-size: 13px; }
.batch-row { padding: 9px 10px; border-radius: 6px; background: #fff; font-size: 12px; }
.batch-row + .batch-row { margin-top: 7px; }
.batch-heading { display: flex; justify-content: space-between; gap: 10px; color: var(--el-text-color-secondary); }
.batch-heading strong { color: var(--erp-text); }
.batch-row p { margin: 6px 0 0; color: var(--el-text-color-secondary); }
.work-order-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.work-order-actions :deep(.el-button) { margin: 0; }
@media (max-width: 1150px) { .metrics { grid-template-columns: repeat(3, 1fr); } }
</style>
