<script setup lang="ts">
import ProcessStepCard, { type ProcessStep } from '@/component/ProcessStepCard.vue'

export type WorkOrderItem = {
  id: string
  part: string
  quantity: number
  status: string
  createdAt: string
  steps: ProcessStep[]
}

defineProps<{
  order: WorkOrderItem
}>()

const emit = defineEmits<{
  outbound: [orderId: string, stepIndex: number, quantity: number]
}>()

function getProgress(step: ProcessStep) {
  if (step.inbound <= 0) {
    return 0
  }

  return Math.min(100, Math.round((step.outbound / step.inbound) * 100))
}
</script>

<template>
  <article class="order-card">
    <div class="order-head">
      <div>
        <div class="order-meta">{{ order.id }} · {{ order.createdAt }}</div>
        <h2>{{ order.part }}</h2>
        <p>计划数量：{{ order.quantity }}</p>
      </div>
      <ElTag :type="order.status === '加工中' ? 'primary' : order.status === '已完成' ? 'success' : 'info'" effect="light">
        {{ order.status }}
      </ElTag>
    </div>

    <div class="process-flow">
      <div v-for="(step, index) in order.steps" :key="`${order.id}-${step.name}`" class="process-node">
        <ProcessStepCard
          :step="step"
          :index="index"
          :progress="getProgress(step)"
          :can-outbound="step.inbound > step.outbound"
          @outbound="(quantity) => emit('outbound', order.id, index, quantity)"
        />

        <div v-if="index < order.steps.length - 1" class="flow-connector">
          <ElProgress :percentage="getProgress(step)" :stroke-width="6" :show-text="false" />
        </div>
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

.flow-connector {
  width: 88px;
  padding: 0 14px;
  flex-shrink: 0;
}
</style>
