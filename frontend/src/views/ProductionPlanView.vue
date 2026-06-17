<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createWorkOrder as createWorkOrderApi, queryWorkOrders } from '@/api/workorder'
import WorkOrderCard from '@/component/WorkOrderCard.vue'
import {
  PROCEDURE_LABELS,
  PROCEDURE_OPTIONS,
  type Procedure,
  type WorkOrderItem,
  type WorkOrderQuery,
  type WorkOrderStatus,
} from '@/types/workorder'

const router = useRouter()
const dialogVisible = ref(false)
const loading = ref(false)
const availableProcedures = [...PROCEDURE_OPTIONS]
const selectedProcedure = ref<Procedure | ''>('laser')

const queryForm = reactive<WorkOrderQuery>({
  orderId: '',
  item: '',
  status: '',
  procedure: '',
})

const form = reactive({
  item: 'MOG3V45-过桥',
  quantity: 100,
  procedures: [] as Procedure[],
})

const proceduresToAdd = computed(() =>
  availableProcedures.filter((procedure) => !form.procedures.includes(procedure)),
)

const statusOptions: WorkOrderStatus[] = ['待开工', '加工中', '已完成']
const workOrders = ref<WorkOrderItem[]>([])

const totalQuantity = computed(() =>
  workOrders.value.reduce((total, order) => total + order.quantity, 0),
)

const activeQuantity = computed(() =>
  workOrders.value.reduce((total, order) => {
    const lastStep = order.steps[order.steps.length - 1]
    return total + (lastStep ? order.quantity - lastStep.outbound : order.quantity)
  }, 0),
)

async function loadWorkOrders() {
  loading.value = true

  try {
    workOrders.value = await queryWorkOrders(queryForm)
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  queryForm.orderId = ''
  queryForm.item = ''
  queryForm.status = ''
  queryForm.procedure = ''
  loadWorkOrders()
}

function openCreateDialog() {
  form.item = 'MOG3V45-过桥'
  form.quantity = 100
  form.procedures = []
  selectedProcedure.value = proceduresToAdd.value[0] ?? 'laser'
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

async function createWorkOrder() {
  if (!form.item.trim() || form.quantity <= 0 || form.procedures.length === 0) {
    return
  }

  await createWorkOrderApi({
    item: form.item.trim(),
    quantity: form.quantity,
    procedures: [...form.procedures],
  })

  dialogVisible.value = false
  await loadWorkOrders()
}

function formatRecordTime(date: Date) {
  const pad = (value: number) => String(value).padStart(2, '0')

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

function getProcedureLabel(procedure: Procedure) {
  return PROCEDURE_LABELS[procedure]
}

function recordOutbound(orderId: string, stepIndex: number, outboundQuantity: number) {
  const order = workOrders.value.find((item) => item.id === orderId)
  const step = order?.steps[stepIndex]

  if (!order || !step || outboundQuantity <= 0 || step.inbound < step.outbound + outboundQuantity) {
    return
  }

  const quantity = outboundQuantity
  step.outbound += quantity
  // step.outboundRecords.unshift({
  //   id: `R-${Date.now()}-${stepIndex}`,
  //   quantity,
  //   createdAt: formatRecordTime(new Date()),
  //   operator: '当前操作员',
  // })

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

onMounted(() => {
  loadWorkOrders()
})
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

    <section class="query-panel">
      <ElForm :model="queryForm" class="query-form" label-position="top">
        <ElFormItem label="工单编号">
          <ElInput v-model="queryForm.orderId" clearable placeholder="例如：MO-20260616" />
        </ElFormItem>
        <ElFormItem label="部件">
          <ElInput v-model="queryForm.item" clearable placeholder="例如：MOG3V45-过桥" />
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSelect v-model="queryForm.status" clearable placeholder="全部状态">
            <ElOption v-for="status in statusOptions" :key="status" :label="status" :value="status" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="包含工序">
          <ElSelect v-model="queryForm.procedure" clearable placeholder="全部工序">
            <ElOption
              v-for="procedure in availableProcedures"
              :key="procedure"
              :label="getProcedureLabel(procedure)"
              :value="procedure"
            />
          </ElSelect>
        </ElFormItem>
        <div class="query-actions">
          <ElButton @click="resetQuery">重置</ElButton>
          <ElButton type="primary" :loading="loading" @click="loadWorkOrders">查询工单</ElButton>
        </div>
      </ElForm>
    </section>

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
        <small>激光 / 冲压 / CNC / 打磨 / QC</small>
      </div>
    </section>

    <section v-loading="loading" class="order-list">
      <WorkOrderCard
        v-for="order in workOrders"
        :key="order.id"
        :order="order"
        @outbound="recordOutbound"
      />
      <ElEmpty v-if="!loading && workOrders.length === 0" description="暂无匹配工单" />
    </section>

    <ElDialog v-model="dialogVisible" title="添加工单" width="560px">
      <ElForm label-position="top">
        <ElFormItem label="部件">
          <ElInput v-model="form.item" placeholder="例如：MOG3V45-过桥" />
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
                  :label="getProcedureLabel(procedure)"
                  :value="procedure"
                />
              </ElSelect>
              <ElButton :disabled="proceduresToAdd.length === 0" @click="addProcedure">加入流程</ElButton>
            </div>

            <div class="ordered-procedures">
              <div v-for="(procedure, index) in form.procedures" :key="procedure" class="procedure-row">
                <div class="procedure-sequence">
                  <span>{{ index + 1 }}</span>
                  <strong>{{ getProcedureLabel(procedure) }}</strong>
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

.query-panel {
  margin-bottom: 18px;
  padding: 18px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--erp-shadow-sm);
}

.query-form {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
  gap: 12px;
  align-items: end;
}

.query-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.query-actions {
  display: flex;
  gap: 8px;
  padding-bottom: 1px;
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
  .query-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .query-actions {
    grid-column: 1 / -1;
  }

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

  .query-form {
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
