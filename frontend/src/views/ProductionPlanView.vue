<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import WorkOrderCard, { type WorkOrderItem } from '@/component/WorkOrderCard.vue'

type ProcedureName = '激光' | 'CNC' | '打磨' | 'QC'

const router = useRouter()
const dialogVisible = ref(false)
const availableProcedures: ProcedureName[] = ['激光', 'CNC', '打磨', 'QC']
const selectedProcedure = ref<ProcedureName | ''>('激光')

const form = reactive({
  part: 'MOG3V45-过桥',
  quantity: 100,
  procedures: [] as ProcedureName[],
})

const proceduresToAdd = computed(() =>
  availableProcedures.filter((procedure) => !form.procedures.includes(procedure)),
)

const workOrders = ref<WorkOrderItem[]>([
  {
    id: 'MO-20260616-001',
    part: 'MOG3V45-过桥',
    quantity: 120,
    status: '加工中',
    createdAt: '2026-06-16',
    steps: [
      {
        name: '激光',
        inbound: 120,
        outbound: 120,
        outboundRecords: [
          { id: 'R-001-1', quantity: 70, createdAt: '2026-06-16 09:12', operator: '张工' },
          { id: 'R-001-2', quantity: 50, createdAt: '2026-06-16 10:24', operator: '张工' },
        ],
      },
      {
        name: 'CNC',
        inbound: 120,
        outbound: 86,
        outboundRecords: [
          { id: 'R-001-3', quantity: 46, createdAt: '2026-06-16 13:18', operator: '李工' },
          { id: 'R-001-4', quantity: 40, createdAt: '2026-06-16 15:06', operator: '李工' },
        ],
      },
      {
        name: '打磨',
        inbound: 86,
        outbound: 42,
        outboundRecords: [
          { id: 'R-001-5', quantity: 42, createdAt: '2026-06-16 16:20', operator: '王工' },
        ],
      },
      {
        name: 'QC',
        inbound: 42,
        outbound: 18,
        outboundRecords: [
          { id: 'R-001-6', quantity: 18, createdAt: '2026-06-16 17:05', operator: '赵工' },
        ],
      },
    ],
  },
  {
    id: 'MO-20260616-002',
    part: 'BRK8A12-固定座',
    quantity: 80,
    status: '待开工',
    createdAt: '2026-06-16',
    steps: [
      { name: '激光', inbound: 80, outbound: 0, outboundRecords: [] },
      { name: 'CNC', inbound: 0, outbound: 0, outboundRecords: [] },
      { name: 'QC', inbound: 0, outbound: 0, outboundRecords: [] },
    ],
  },
])

const totalQuantity = computed(() =>
  workOrders.value.reduce((total, order) => total + order.quantity, 0),
)

const activeQuantity = computed(() =>
  workOrders.value.reduce((total, order) => {
    const lastStep = order.steps[order.steps.length - 1]
    return total + (lastStep ? order.quantity - lastStep.outbound : order.quantity)
  }, 0),
)

function openCreateDialog() {
  form.part = 'MOG3V45-过桥'
  form.quantity = 100
  form.procedures = []
  selectedProcedure.value = proceduresToAdd.value[0] ?? '激光'
  dialogVisible.value = true
}

function addProcedure() {
  if (!selectedProcedure.value || form.procedures.includes(selectedProcedure.value)) {
    return
  }

  form.procedures.push(selectedProcedure.value)
  selectedProcedure.value = proceduresToAdd.value[0] ?? ''
}

function removeProcedure(index: number) {
  form.procedures.splice(index, 1)
  selectedProcedure.value = proceduresToAdd.value[0] ?? ''
}

function moveProcedure(index: number, direction: -1 | 1) {
  const targetIndex = index + direction

  if (targetIndex < 0 || targetIndex >= form.procedures.length) {
    return
  }

  const current = form.procedures[index]
  const target = form.procedures[targetIndex]

  if (!current || !target) {
    return
  }

  form.procedures[index] = target
  form.procedures[targetIndex] = current
}

function createWorkOrder() {
  if (!form.part.trim() || form.quantity <= 0 || form.procedures.length === 0) {
    return
  }

  const id = `MO-${new Date().getTime()}`
  const steps = form.procedures.map((name, index) => ({
    name,
    inbound: index === 0 ? form.quantity : 0,
    outbound: 0,
    outboundRecords: [],
  }))

  workOrders.value.unshift({
    id,
    part: form.part.trim(),
    quantity: form.quantity,
    status: '待开工',
    createdAt: '今日',
    steps,
  })

  dialogVisible.value = false
}

function formatRecordTime(date: Date) {
  const pad = (value: number) => String(value).padStart(2, '0')

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

function recordOutbound(orderId: string, stepIndex: number, outboundQuantity: number) {
  const order = workOrders.value.find((item) => item.id === orderId)
  const step = order?.steps[stepIndex]

  if (!order || !step || outboundQuantity <= 0 || step.inbound < step.outbound + outboundQuantity) {
    return
  }

  const quantity = outboundQuantity
  step.outbound += quantity
  step.outboundRecords.unshift({
    id: `R-${Date.now()}-${stepIndex}`,
    quantity,
    createdAt: formatRecordTime(new Date()),
    operator: '当前操作员',
  })

  const nextStep = order.steps[stepIndex + 1]
  if (nextStep) {
    nextStep.inbound += quantity
  } else {
    order.status = '已完成'
  }

  if (order.status === '待开工') {
    order.status = '加工中'
  }
}
</script>

<template>
  <main class="production-page">
    <header class="production-header">
      <div>
        <ElButton text class="back-button" @click="router.push('/')">返回导航</ElButton>
        <div class="page-kicker">Production Planning</div>
        <h1>生产计划</h1>
        <p>围绕工单组织部件、数量和工序流转，按入库与出库数量查看每道工序的推进情况。</p>
      </div>
      <div class="header-actions">
        <ElButton>导出排程</ElButton>
        <ElButton type="primary" @click="openCreateDialog">添加工单</ElButton>
      </div>
    </header>

    <section class="summary-grid">
      <div class="summary-card">
        <span>工单数量</span>
        <strong>{{ workOrders.length }}</strong>
        <small>今日计划</small>
      </div>
      <div class="summary-card">
        <span>计划数量</span>
        <strong>{{ totalQuantity }}</strong>
        <small>全部部件</small>
      </div>
      <div class="summary-card">
        <span>在制数量</span>
        <strong>{{ activeQuantity }}</strong>
        <small>未完成流转</small>
      </div>
      <div class="summary-card">
        <span>标准工序</span>
        <strong>{{ availableProcedures.length }}</strong>
        <small>激光 / CNC / 打磨 / QC</small>
      </div>
    </section>

    <section class="order-list">
      <WorkOrderCard
        v-for="order in workOrders"
        :key="order.id"
        :order="order"
        @outbound="recordOutbound"
      />
    </section>

    <ElDialog v-model="dialogVisible" title="添加工单" width="560px">
      <ElForm label-position="top">
        <ElFormItem label="部件">
          <ElInput v-model="form.part" placeholder="例如：MOG3V45-过桥" />
        </ElFormItem>

        <ElFormItem label="数量">
          <ElInputNumber v-model="form.quantity" :min="1" :step="1" controls-position="right" />
        </ElFormItem>

        <ElFormItem label="工序流程">
          <div class="procedure-builder">
            <div class="procedure-picker">
              <ElSelect v-model="selectedProcedure" :disabled="proceduresToAdd.length === 0" placeholder="选择工序">
                <ElOption
                  v-for="procedure in proceduresToAdd"
                  :key="procedure"
                  :label="procedure"
                  :value="procedure"
                />
              </ElSelect>
              <ElButton :disabled="proceduresToAdd.length === 0" @click="addProcedure">加入流程</ElButton>
            </div>

            <div class="ordered-procedures">
              <div v-for="(procedure, index) in form.procedures" :key="procedure" class="procedure-row">
                <div class="procedure-sequence">
                  <span>{{ index + 1 }}</span>
                  <strong>{{ procedure }}</strong>
                </div>
                <div class="procedure-actions">
                  <ElButton text :disabled="index === 0" @click="moveProcedure(index, -1)">上移</ElButton>
                  <ElButton text :disabled="index === form.procedures.length - 1" @click="moveProcedure(index, 1)">
                    下移
                  </ElButton>
                  <ElButton text type="danger" @click="removeProcedure(index)">移除</ElButton>
                </div>
              </div>
              <ElEmpty v-if="form.procedures.length === 0" description="请按加工顺序加入工序" :image-size="72" />
            </div>
          </div>
        </ElFormItem>
      </ElForm>

      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="form.procedures.length === 0" @click="createWorkOrder">
          确认添加
        </ElButton>
      </template>
    </ElDialog>
  </main>
</template>

<style scoped>
.production-page {
  min-height: 100vh;
  padding: 22px;
  background:
    linear-gradient(180deg, #f8fafc 0, #edf1f5 320px),
    #edf1f5;
}

.production-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 26px 30px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgb(37 99 235 / 94%), rgb(8 145 178 / 88%)),
    #2563eb;
  color: #ffffff;
  box-shadow: var(--erp-shadow-md);
}

.back-button {
  margin: 0 0 12px -12px;
  color: #dbeafe;
}

.page-kicker {
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.production-header h1 {
  margin: 8px 0 10px;
  font-size: 32px;
  line-height: 1.2;
}

.production-header p {
  max-width: 720px;
  margin: 0;
  color: #e5f2ff;
  font-size: 14px;
  line-height: 1.7;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.header-actions :deep(.el-button:not(.el-button--primary)) {
  border-color: rgb(255 255 255 / 68%);
  background: rgb(255 255 255 / 14%);
  color: #ffffff;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.summary-card {
  padding: 18px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--erp-shadow-sm);
}

.summary-card span,
.summary-card small {
  display: block;
  color: var(--erp-text-muted);
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin: 8px 0 6px;
  color: var(--erp-text);
  font-size: 28px;
}

.order-list {
  display: grid;
  gap: 18px;
}

.procedure-builder {
  display: grid;
  gap: 12px;
  width: 100%;
}

.procedure-picker {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}

.ordered-procedures {
  display: grid;
  gap: 8px;
}

.procedure-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: var(--erp-surface-muted);
}

.procedure-sequence {
  display: flex;
  align-items: center;
  gap: 10px;
}

.procedure-sequence span {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 700;
}

.procedure-sequence strong {
  color: var(--erp-text);
}

.procedure-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 2px;
}

@media (max-width: 1180px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .production-header {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 760px) {
  .production-page {
    padding: 14px;
  }

  .production-header {
    padding: 22px;
  }

  .production-header h1 {
    font-size: 26px;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .procedure-picker,
  .procedure-row {
    grid-template-columns: 1fr;
  }

  .procedure-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
