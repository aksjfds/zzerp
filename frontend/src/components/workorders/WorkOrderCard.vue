<script setup lang="ts">
import ProcessStepCard from '@/components/workorders/ProcessStepCard.vue'
import type { WorkOrderItem } from '@/types/workorder'

defineProps<{
  order: WorkOrderItem
}>()

const emit = defineEmits<{
  changed: []
}>()
</script>

<template>
  <article class="order-card">
    <div class="order-head">
      <div>
        <div class="order-meta">{{ order.id }} · {{ order.createdAt }}</div>
        <h2>{{ order.item }}</h2>
        <p>计划数量：{{ order.quantity }}</p>
      </div>
      <ElTag :type="order.status === '加工中' ? 'primary' : order.status === '已完成' ? 'success' : 'info'" effect="light">
        {{ order.status }}
      </ElTag>
    </div>

    <div class="process-flow">
      <div v-for="(step, index) in order.steps" :key="`${order.id}-${step.name}`" class="process-node">
        <ProcessStepCard
          :order-id="order.id"
          :item="order.item"
          :step="step"
          :index="index"
          :can-outbound="step.quantity > 0"
          :can-rework="index > 0 && step.quantity > 0"
          :outbound-target="order.steps[index + 1]?.name ?? 'out'"
          :rework-target="order.steps[index - 1]?.name"
          @changed="emit('changed')"
        />
      </div>
    </div>
  </article>
</template>

<style scoped>
.order-card {
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--erp-shadow-sm);
}

.order-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.order-meta {
  color: var(--erp-text-muted);
  font-size: 13px;
}

.order-head h2 {
  margin: 6px 0;
  color: var(--erp-text);
  font-size: 20px;
}

.order-head p {
  margin: 0;
  color: var(--erp-text-secondary);
}

.process-flow {
  display: flex;
  align-items: stretch;
  gap: 0;
  overflow-x: auto;
  padding-bottom: 4px;
}

.process-node {
  display: flex;
  align-items: center;
  min-width: 248px;
}

</style>
