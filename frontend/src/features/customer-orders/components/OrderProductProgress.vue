<script setup lang="ts">
import { computed } from 'vue'
import type { CustomerOrderProductProgress } from '../domain/types'

const props = defineProps<{ progress: CustomerOrderProductProgress }>()

const segments = computed(() => {
  const total = Math.max(props.progress.total_quantity, 1)
  return [
    { key: 'completed', title: '已发货', value: props.progress.completed_quantity, width: props.progress.completed_quantity / total * 100 },
    { key: 'scrap', title: '报废', value: props.progress.scrap_quantity, width: props.progress.scrap_quantity / total * 100 },
    { key: 'lost', title: '遗失', value: props.progress.lost_quantity, width: props.progress.lost_quantity / total * 100 },
    { key: 'unfinished', title: '未完工', value: props.progress.unfinished_quantity, width: props.progress.unfinished_quantity / total * 100 },
  ]
})
</script>

<template>
  <section class="product-progress">
    <div class="product-heading">
      <strong>{{ progress.factory_code }} · {{ progress.product_name }}</strong>
      <ElTag v-if="progress.po_shortage_quantity" type="warning" effect="light">
        欠 PO {{ progress.po_shortage_quantity }}
      </ElTag>
    </div>
    <div class="progress-track" :aria-label="`${progress.product_name}生产进度`">
      <span
        v-for="segment in segments"
        :key="segment.key"
        class="progress-segment"
        :class="segment.key"
        :style="{ width: `${segment.width}%` }"
        :title="`${segment.title} ${segment.value}`"
      />
    </div>
    <div class="progress-values">
      <span>总数 <b>{{ progress.total_quantity }}</b></span>
      <span class="completed">已发货 <b>{{ progress.completed_quantity }}</b></span>
      <span class="scrap">报废 <b>{{ progress.scrap_quantity }}</b></span>
      <span class="lost">遗失 <b>{{ progress.lost_quantity }}</b></span>
      <span>未完工 <b>{{ progress.unfinished_quantity }}</b></span>
      <span class="po">欠 PO <b>{{ progress.po_shortage_quantity }}</b></span>
    </div>
  </section>
</template>

<style scoped>
.product-progress + .product-progress { margin-top: 14px; padding-top: 14px; border-top: 1px dashed var(--erp-border); }
.product-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 8px; }
.product-heading strong { font-size: 13px; }
.progress-track { display: flex; width: 100%; height: 10px; overflow: hidden; border-radius: 999px; background: var(--md-surface-container-highest); }
.progress-segment { min-width: 0; height: 100%; }
.progress-segment.completed { background: var(--erp-success); }
.progress-segment.scrap { background: var(--md-error); }
.progress-segment.lost { background: var(--md-secondary); }
.progress-segment.unfinished { background: var(--md-outline-variant); }
.progress-values { display: grid; grid-template-columns: repeat(6, minmax(max-content, 1fr)); gap: 6px 12px; margin-top: 8px; color: var(--el-text-color-secondary); font-size: 12px; }
.progress-values b { color: var(--el-text-color-primary); }
.progress-values .completed b { color: var(--erp-success); }
.progress-values .scrap b { color: var(--md-error); }
.progress-values .lost b { color: var(--md-secondary); }
.progress-values .po b { color: var(--erp-warning); }
@media (max-width: 900px) { .progress-values { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 520px) {
  .product-heading { align-items: flex-start; flex-direction: column; }
  .progress-values { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
