<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ProcessStep } from '@/types/workorder'

const emit = defineEmits<{
  outbound: [quantity: number]
}>()

const props = defineProps<{
  step: ProcessStep
  index: number
  progress: number
  canOutbound: boolean
}>()

const popoverVisible = ref(false)
const outboundQuantity = ref(1)

const remainingQuantity = computed(() => Math.max(0, props.step.inbound - props.step.outbound))

watch(
  remainingQuantity,
  (quantity) => {
    outboundQuantity.value = quantity > 0 ? Math.min(outboundQuantity.value, quantity) || 1 : 0
  },
  { immediate: true },
)

function submitOutbound() {
  if (!props.canOutbound || outboundQuantity.value <= 0 || outboundQuantity.value > remainingQuantity.value) {
    return
  }

  emit('outbound', outboundQuantity.value)
}
</script>

<template>
  <ElPopover
    v-model:visible="popoverVisible"
    trigger="click"
    placement="right"
    :width="360"
    popper-class="process-history-popover"
  >
    <template #reference>
      <ElCard shadow="never" class="process-card">
        <div class="process-card-head">
          <span class="step-index">{{ index + 1 }}</span>
          <strong>{{ step.name }}</strong>
        </div>

        <div class="quantity-pair">
          <div>
            <span>上工序入库</span>
            <strong>{{ step.inbound }}</strong>
          </div>
          <div>
            <span>送下工序出库</span>
            <strong>{{ step.outbound }}</strong>
          </div>
        </div>

        <ElProgress :percentage="progress" :stroke-width="8" :show-text="false" status="success" />
        <div class="progress-label">
          <span>出库 / 入库</span>
          <strong>{{ progress }}%</strong>
        </div>
      </ElCard>
    </template>

    <div class="history-panel">
      <div class="history-head">
        <strong>{{ step.name }} 出库记录</strong>
        <span>{{ step.outboundRecords.length }} 次操作</span>
      </div>

      <div class="outbound-form">
        <div>
          <span>可出库数量</span>
          <strong>{{ remainingQuantity }}</strong>
        </div>
        <ElInputNumber
          v-model="outboundQuantity"
          :min="1"
          :max="remainingQuantity || 1"
          :disabled="!canOutbound"
          controls-position="right"
        />
        <ElButton type="primary" :disabled="!canOutbound" @click="submitOutbound">确认出库</ElButton>
      </div>

      <ElTimeline v-if="step.outboundRecords.length > 0">
        <ElTimelineItem
          v-for="record in step.outboundRecords"
          :key="record.id"
          :timestamp="record.createdAt"
          placement="top"
        >
          <div class="history-item">
            <strong>出库 {{ record.quantity }}</strong>
            <span>操作人：{{ record.operator }}</span>
          </div>
        </ElTimelineItem>
      </ElTimeline>

      <ElEmpty v-else description="暂无出库记录" :image-size="72" />
    </div>
  </ElPopover>
</template>

<style scoped>
.process-card {
  width: 248px;
  min-height: 178px;
  border-color: var(--erp-border);
  border-radius: 8px;
  background: var(--erp-surface-muted);
  cursor: pointer;
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.process-card:hover {
  border-color: #b8c7d9;
  box-shadow: 0 14px 28px rgb(15 23 42 / 9%);
  transform: translateY(-1px);
}

.process-card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.step-index {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 700;
}

.quantity-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.quantity-pair div {
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.quantity-pair span,
.progress-label span {
  display: block;
  color: var(--erp-text-muted);
  font-size: 12px;
}

.quantity-pair strong {
  display: block;
  margin-top: 4px;
  color: var(--erp-text);
  font-size: 18px;
}

.progress-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.progress-label strong {
  color: var(--erp-success);
}

.history-panel {
  padding: 2px 0;
}

.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.history-head strong {
  color: var(--erp-text);
}

.history-head span {
  color: var(--erp-text-muted);
  font-size: 12px;
}

.outbound-form {
  display: grid;
  grid-template-columns: 1fr 128px;
  gap: 10px;
  align-items: end;
  margin-bottom: 16px;
  padding: 12px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: var(--erp-surface-muted);
}

.outbound-form > div span {
  display: block;
  color: var(--erp-text-muted);
  font-size: 12px;
}

.outbound-form > div strong {
  display: block;
  margin-top: 4px;
  color: var(--erp-text);
  font-size: 20px;
}

.outbound-form :deep(.el-button) {
  grid-column: 1 / -1;
}

.history-item {
  display: grid;
  gap: 4px;
}

.history-item strong {
  color: var(--erp-text);
}

.history-item span {
  color: var(--erp-text-muted);
  font-size: 12px;
}
</style>
