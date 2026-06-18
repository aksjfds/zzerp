<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { queryOperationRecords, recordOutbound, recordRework } from '@/api/workorder'
import { PROCEDURE_LABELS, type Procedure, type ProcessStep } from '@/types/workorder'

const emit = defineEmits<{
  changed: []
}>()

const props = defineProps<{
  orderId: string
  item: string
  step: ProcessStep
  index: number
  canOutbound: boolean
  canRework: boolean
  outboundTarget: Procedure | 'out'
  reworkTarget?: Procedure
}>()

const popoverVisible = ref(false)
const outboundQuantity = ref(1)
const outboundNote = ref('')
const workerName = ref('')
const logsLoading = ref(false)
const submitting = ref(false)
const operationRecords = ref<Awaited<ReturnType<typeof queryOperationRecords>>>([])

const availableQuantity = computed(() => props.step.quantity)
const procedureLabel = computed(() => PROCEDURE_LABELS[props.step.name])
const needsWorkerForOutbound = computed(() => props.step.name === 'polish' && props.outboundTarget === 'qc')
const needsWorkerForRework = computed(() => props.step.name === 'qc' && props.reworkTarget === 'polish')
const trimmedWorkerName = computed(() => workerName.value.trim())

watch(
  availableQuantity,
  (quantity) => {
    outboundQuantity.value = quantity > 0 ? Math.min(outboundQuantity.value, quantity) || 1 : 0
  },
  { immediate: true },
)

async function loadOperationRecords() {
  logsLoading.value = true

  try {
    operationRecords.value = await queryOperationRecords(props.orderId, props.item, props.step.name)
  } finally {
    logsLoading.value = false
  }
}

async function submitOutbound() {
  if (!props.canOutbound || outboundQuantity.value <= 0 || outboundQuantity.value > availableQuantity.value) {
    return
  }

  submitting.value = true

  try {
    await recordOutbound({
      orderId: props.orderId,
      item: props.item,
      repository: props.step.name,
      quantity: outboundQuantity.value,
      operator: '当前操作员',
      worker: needsWorkerForOutbound.value ? trimmedWorkerName.value || undefined : undefined,
      note: outboundNote.value.trim() || undefined,
    })
    outboundNote.value = ''
    if (needsWorkerForOutbound.value) {
      workerName.value = ''
    }
    await loadOperationRecords()
    emit('changed')
  } finally {
    submitting.value = false
  }
}

async function submitRework() {
  if (!props.canRework || outboundQuantity.value <= 0 || outboundQuantity.value > availableQuantity.value) {
    return
  }

  submitting.value = true

  try {
    await recordRework({
      orderId: props.orderId,
      item: props.item,
      repository: props.step.name,
      quantity: outboundQuantity.value,
      operator: '当前操作员',
      worker: needsWorkerForRework.value ? trimmedWorkerName.value || undefined : undefined,
      note: outboundNote.value.trim() || undefined,
    })
    outboundNote.value = ''
    if (needsWorkerForRework.value) {
      workerName.value = ''
    }
    await loadOperationRecords()
    emit('changed')
  } finally {
    submitting.value = false
  }
}

function formatRepository(repository?: string | null) {
  if (!repository) {
    return '-'
  }

  if (repository === 'in') {
    return '入库'
  }

  if (repository === 'out') {
    return '完工'
  }

  return PROCEDURE_LABELS[repository as keyof typeof PROCEDURE_LABELS] ?? repository
}
</script>

<template>
  <ElPopover
    v-model:visible="popoverVisible"
    trigger="click"
    placement="right"
    :width="360"
    popper-class="process-history-popover"
    @show="loadOperationRecords"
  >
    <template #reference>
      <ElCard shadow="never" class="process-card">
        <div class="process-card-head">
          <span class="step-index">{{ index + 1 }}</span>
          <strong>{{ procedureLabel }}</strong>
        </div>

        <div class="quantity-single">
          <span>当前数量</span>
          <strong>{{ step.quantity }}</strong>
        </div>
      </ElCard>
    </template>

    <div v-loading="logsLoading" class="history-panel">
      <div class="history-head">
        <strong>{{ procedureLabel }} 操作记录</strong>
        <span>{{ operationRecords.length }} 次操作</span>
      </div>

      <div class="operation-form">
        <div>
          <span>当前数量</span>
          <strong>{{ availableQuantity }}</strong>
        </div>
        <ElInputNumber
          v-model="outboundQuantity"
          class="operation-input"
          :min="1"
          :max="availableQuantity || 1"
          :disabled="availableQuantity <= 0"
          :controls="false"
        />
        <ElInput
          v-if="needsWorkerForOutbound || needsWorkerForRework"
          v-model="workerName"
          placeholder="打磨工人"
          maxlength="100"
          show-word-limit
        />
        <ElInput v-model="outboundNote" type="textarea" placeholder="备注" maxlength="255" show-word-limit />
        <div class="operation-actions">
          <ElButton type="primary" :disabled="!canOutbound" :loading="submitting" @click="submitOutbound">
            确认出库
          </ElButton>
          <ElButton :disabled="!canRework" :loading="submitting" @click="submitRework">
            返工到上工序
          </ElButton>
        </div>
      </div>

      <ElTimeline :reverse="true" v-if="operationRecords.length > 0">
        <ElTimelineItem
          v-for="record in operationRecords"
          :key="record.id"
          :timestamp="record.createdAt"
          placement="top"
        >
          <div class="history-item">
            <strong>
              {{ formatRepository(record.fromRepository) }} -> {{ formatRepository(record.toRepository) }}
              {{ record.quantity }}
            </strong>
            <span v-if="record.worker">打磨工人：{{ record.worker }}</span>
            <span>操作人：{{ record.operator || '-' }}</span>
            <span v-if="record.note">备注：{{ record.note }}</span>
          </div>
        </ElTimelineItem>
      </ElTimeline>

      <ElEmpty v-else description="暂无操作记录" :image-size="72" />
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

.quantity-single {
  display: grid;
  gap: 4px;
  margin-bottom: 16px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.quantity-single span {
  display: block;
  color: var(--erp-text-muted);
  font-size: 12px;
}

.quantity-single strong {
  display: block;
  color: var(--erp-text);
  font-size: 28px;
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

.operation-form {
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

.operation-form > div span {
  display: block;
  color: var(--erp-text-muted);
  font-size: 12px;
}

.operation-form > div strong {
  display: block;
  margin-top: 4px;
  color: var(--erp-text);
  font-size: 20px;
}

.operation-form :deep(.el-input),
.operation-form :deep(.el-textarea),
.operation-actions {
  grid-column: 1 / -1;
}

.operation-actions {
  display: flex;
  gap: 8px;
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
