<script setup lang="ts">
import ProductionProgressWorkOrders from './ProductionProgressWorkOrders.vue'
import type { ProductionProgressProcedureCard } from '../domain/productionProgress'
import {
  currentProgressQuantity,
  displayWorkshopName,
  exceptionQuantity,
  progressCardStatusLabels,
  progressCardStatusTypes,
  segmentProgressWidth,
} from '../domain/progressPresentation'

defineProps<{
  card: ProductionProgressProcedureCard
  focused: boolean
}>()
</script>

<template>
  <article class="tag-progress-card" :class="{ focused }">
    <header class="card-header">
      <div>
        <div class="card-title-row">
          <h3>{{ card.card_name }}</h3>
          <ElTag size="small" type="info" effect="plain">
            {{ card.card_type === 'assembly' ? '装配' : card.card_type === 'purchase' ? '外购' : '加工' }}
          </ElTag>
        </div>
        <p>{{ card.department_name }} · {{ displayWorkshopName(card.workshop_name) }} · {{ card.procedure_name }}</p>
      </div>
      <ElTag :type="progressCardStatusTypes[card.status]" effect="light">
        {{ progressCardStatusLabels[card.status] }}
      </ElTag>
    </header>

    <div class="quantity-progress">
      <div class="quantity-progress-track" role="progressbar" :aria-label="`${card.card_name}加工进度`"
        aria-valuemin="0" :aria-valuemax="card.task_quantity" :aria-valuenow="currentProgressQuantity(card)">
        <span class="quantity-progress-segment completed" :style="{ width: segmentProgressWidth(card, 'completed') }" />
        <span class="quantity-progress-segment exception" :style="{ width: segmentProgressWidth(card, 'exception') }" />
        <span class="quantity-progress-segment submitted" :style="{ width: segmentProgressWidth(card, 'submitted') }" />
        <span class="quantity-progress-segment processing" :style="{ width: segmentProgressWidth(card, 'processing') }" />
      </div>
      <div class="quantity-progress-legend">
        <span class="completed">已完成</span><span class="exception">异常</span>
        <span class="submitted">送检中</span><span class="processing">加工中</span>
      </div>
    </div>

    <dl class="card-metrics">
      <div><dt>任务数量</dt><dd>{{ card.task_quantity }}</dd></div>
      <div><dt>加工中</dt><dd>{{ card.processing_quantity }}</dd></div>
      <div><dt>送检中</dt><dd>{{ card.pending_qc_quantity }}</dd></div>
      <div><dt>QC 合格</dt><dd>{{ card.completed_quantity }}</dd></div>
      <div><dt>异常数量</dt><dd :class="{ danger: exceptionQuantity(card) > 0 }">{{ exceptionQuantity(card) }}</dd></div>
    </dl>

    <div v-if="exceptionQuantity(card)" class="exception-summary">
      <strong>异常明细</strong><span>返工 {{ card.rework_quantity }}</span>
      <span>报废 {{ card.scrap_quantity }}</span><span>丢失 {{ card.lost_quantity }}</span>
    </div>
    <ProductionProgressWorkOrders :work-orders="card.work_orders" />
  </article>
</template>

<style scoped>
.tag-progress-card { min-width: 0; padding: 18px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.tag-progress-card.focused { border-color: var(--md-primary); box-shadow: 0 0 0 2px color-mix(in srgb, var(--md-primary) 18%, transparent); }
.card-header, .card-title-row { display: flex; align-items: center; gap: 8px; }
.card-header { align-items: flex-start; justify-content: space-between; margin-bottom: 14px; }
.card-header h3, .card-header p { margin: 0; }
.card-header h3 { font-size: 18px; }
.card-header p { margin-top: 5px; color: var(--md-on-surface-variant); font-size: 13px; }
.quantity-progress-track { display: flex; width: 100%; height: 12px; overflow: hidden; border-radius: 999px; background: var(--md-surface-container-high); }
.quantity-progress-segment { flex: 0 0 auto; height: 100%; }
.quantity-progress-segment.completed, .quantity-progress-legend .completed::before { background: var(--el-color-success); }
.quantity-progress-segment.exception, .quantity-progress-legend .exception::before { background: var(--el-color-danger); }
.quantity-progress-segment.processing, .quantity-progress-legend .processing::before { background: #f4b400; }
.quantity-progress-segment.submitted, .quantity-progress-legend .submitted::before { background: #7e57c2; }
.quantity-progress-legend { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 8px; color: var(--md-on-surface-variant); font-size: 12px; }
.quantity-progress-legend span::before { display: inline-block; width: 8px; height: 8px; margin-right: 6px; border-radius: 50%; content: ''; }
.card-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 16px 0 0; }
.card-metrics div { padding: 10px; border-radius: var(--erp-radius-md); background: var(--md-surface-container-low); }
.card-metrics dt { color: var(--md-on-surface-variant); font-size: 12px; }
.card-metrics dd { margin: 4px 0 0; font-size: 17px; font-weight: 700; }
.danger { color: var(--erp-danger); }
.exception-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 18px; margin-top: 12px; padding: 10px 12px; border: 1px solid color-mix(in srgb, var(--el-color-danger) 45%, transparent); border-radius: var(--erp-radius-md); color: var(--el-color-danger); background: color-mix(in srgb, var(--el-color-danger) 8%, transparent); font-size: 13px; }
@media (max-width: 680px) { .card-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
