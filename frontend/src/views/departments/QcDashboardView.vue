<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useProductsStore } from '@/stores/products'
import { useWorkOrdersStore } from '@/stores/workOrders'
import { DEPARTMENT_LABELS } from '@/types/production'
import type {
  DepartmentProcessItem,
  DirectReportPayload,
  InspectionPayload,
  PendingQcBatch,
  ProductItem,
  WorkOrderItem,
} from '@/types/production'

const router = useRouter()
const authStore = useAuthStore()
const productsStore = useProductsStore()
const workOrdersStore = useWorkOrdersStore()
const { products } = storeToRefs(productsStore)
const { loading, pendingQc, processes, workers, workOrders } = storeToRefs(workOrdersStore)
const inspectionDialogVisible = ref(false)
const assignmentDialogVisible = ref(false)
const workerDialogVisible = ref(false)
const activeBatch = ref<PendingQcBatch | null>(null)
const activeProduct = ref<ProductItem | null>(null)
const activeProcess = ref<DepartmentProcessItem | null>(null)
const activeWorkOrder = ref<WorkOrderItem | null>(null)
const workerName = ref('')
const assignmentWorkerId = ref(0)
const workOrderDialogVisible = ref(false)
const directDialogVisible = ref(false)
const workOrderForm = reactive({ workerId: 0, quantity: 1, note: '' })
const directForm = reactive<DirectReportPayload>({
  okQuantity: 0,
  scrapQuantity: 0,
  lostQuantity: 0,
  reason: '',
})
const form = reactive<InspectionPayload>({
  okQuantity: 0,
  reworkQuantity: 0,
  scrapQuantity: 0,
  lostQuantity: 0,
  defectReason: '',
})

const resultTotal = computed(
  () => form.okQuantity + form.reworkQuantity + form.scrapQuantity + form.lostQuantity,
)
const resultMatches = computed(
  () => Boolean(activeBatch.value && resultTotal.value === activeBatch.value.submittedQuantity),
)
const directTotal = computed(
  () => directForm.okQuantity + directForm.scrapQuantity + directForm.lostQuantity,
)
const externalPendingQc = computed(() =>
  pendingQc.value.filter((batch) => batch.ownerDepartment !== 'qc'),
)
const officialQcProducts = computed(() =>
  products.value.filter((product) =>
    product.repositories.some(
      (repository) => repository.department === 'qc' && repository.quantity > 0,
    ),
  ),
)

function productProcesses(productId: number) {
  return processes.value.filter((item) => item.productId === productId)
}

async function configureOfficialQc(product: ProductItem) {
  try {
    await workOrdersStore.configureProcesses('qc', product.id, [
      { processName: '终检', requiresQc: false },
    ])
    ElMessage.success('已配置 QC 终检工艺')
  } catch {
    ElMessage.error('QC 工艺配置失败')
  }
}

function openOfficialWorkOrder(product: ProductItem, process: DepartmentProcessItem) {
  activeProduct.value = product
  activeProcess.value = process
  workOrderForm.workerId = workers.value[0]?.id ?? 0
  workOrderForm.quantity = process.availableQuantity > 0 ? 1 : 0
  workOrderForm.note = ''
  workOrderDialogVisible.value = true
}

async function submitOfficialWorkOrder() {
  if (!activeProduct.value || !activeProcess.value || !workOrderForm.workerId) {
    ElMessage.warning('请选择 QC 工人')
    return
  }
  try {
    await workOrdersStore.addWorkOrder('qc', {
      productId: activeProduct.value.id,
      processId: activeProcess.value.id,
      workerId: workOrderForm.workerId,
      quantity: workOrderForm.quantity,
      note: workOrderForm.note,
    })
    workOrderDialogVisible.value = false
    ElMessage.success('QC 工单已创建')
  } catch {
    ElMessage.error('QC 工单创建失败')
  }
}

function openDirectReport(item: WorkOrderItem) {
  activeWorkOrder.value = item
  directForm.okQuantity = 0
  directForm.scrapQuantity = 0
  directForm.lostQuantity = 0
  directForm.reason = ''
  directDialogVisible.value = true
}

async function submitDirectReport() {
  if (!activeWorkOrder.value || directTotal.value <= 0) {
    ElMessage.warning('本次报工数量必须大于 0')
    return
  }
  try {
    await workOrdersStore.reportDirect('qc', activeWorkOrder.value.id, directForm)
    directDialogVisible.value = false
    await productsStore.loadProducts()
    ElMessage.success('QC 工单报工已提交')
  } catch {
    ElMessage.error('QC 工单报工失败')
  }
}

function openInspection(batch: PendingQcBatch) {
  if (!batch.qcWorkerId) {
    ElMessage.warning('请先分配 QC 工人')
    return
  }
  activeBatch.value = batch
  form.okQuantity = batch.submittedQuantity
  form.reworkQuantity = 0
  form.scrapQuantity = 0
  form.lostQuantity = 0
  form.defectReason = ''
  inspectionDialogVisible.value = true
}

async function submitInspection() {
  if (!activeBatch.value || !resultMatches.value) {
    ElMessage.warning('结果数量之和必须等于送检数量')
    return
  }
  try {
    await workOrdersStore.inspect(activeBatch.value.id, form)
    inspectionDialogVisible.value = false
    await Promise.all([
      productsStore.loadProducts(),
      workOrdersStore.loadDepartment('qc'),
    ])
    ElMessage.success('质检结果已提交，记录不可修改')
  } catch {
    ElMessage.error('质检提交失败，请检查数量')
  }
}

function openAssignment(batch: PendingQcBatch) {
  activeBatch.value = batch
  assignmentWorkerId.value = batch.qcWorkerId ?? workers.value[0]?.id ?? 0
  assignmentDialogVisible.value = true
}

async function submitAssignment() {
  if (!activeBatch.value || !assignmentWorkerId.value) {
    ElMessage.warning('请选择 QC 工人')
    return
  }
  try {
    await workOrdersStore.assignQcWorker(activeBatch.value.id, assignmentWorkerId.value)
    assignmentDialogVisible.value = false
    ElMessage.success('待质检批次已分配')
  } catch {
    ElMessage.error('分配失败，请确认批次和 QC 工人状态')
  }
}

async function submitWorker() {
  if (!workerName.value.trim()) {
    return
  }
  try {
    await workOrdersStore.addWorker('qc', workerName.value)
    workerName.value = ''
    workerDialogVisible.value = false
    ElMessage.success('QC 工人已添加')
  } catch {
    ElMessage.error('添加 QC 工人失败')
  }
}

async function logout() {
  await authStore.logout()
  router.replace('/login')
}

async function loadDashboard() {
  await productsStore.loadProducts()
  await workOrdersStore.loadDepartment('qc')
  await workOrdersStore.loadPendingQc()
}

onMounted(loadDashboard)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <div class="page-kicker">Quality Control</div>
        <h1>QC 质检台</h1>
        <p>处理各部门内部送检批次；提交后的结果不可修改或删除。</p>
      </div>
      <div class="header-actions">
        <ElButton v-permission="'task:assign'" @click="workerDialogVisible = true">
          添加 QC 工人
        </ElButton>
        <ElButton @click="logout">退出</ElButton>
      </div>
    </header>

    <div v-loading="loading" class="workspace-layout">
      <section class="section-card source-panel">
        <h2>QC 待办与正式库存</h2>

        <div class="panel-block">
          <div class="block-heading">
            <h3>来自其他部门的待质检工单</h3>
            <span>{{ externalPendingQc.length }} 个批次</span>
          </div>
          <div class="submission-list">
            <article
              v-for="batch in externalPendingQc"
              :key="batch.id"
              class="submission-card"
            >
              <div>
                <span>
                  {{ batch.workOrderNo }} · {{ DEPARTMENT_LABELS[batch.ownerDepartment] }}工单
                </span>
                <strong>{{ batch.productName }} / {{ batch.processName }}</strong>
                <em>
                  订单 {{ batch.orderId }} · {{ batch.zzCode }} · 原工人 {{ batch.workerName }}
                </em>
              </div>
              <div class="submission-actions">
                <strong>送检 {{ batch.submittedQuantity }}</strong>
                <ElTag v-if="batch.qcWorkerName" type="success">
                  已分配：{{ batch.qcWorkerName }}
                </ElTag>
                <ElTag v-else type="warning">待分配</ElTag>
                <ElButton
                  v-permission="'task:assign'"
                  size="small"
                  @click="openAssignment(batch)"
                >
                  {{ batch.qcWorkerId ? '重新分配' : '分配 QC 工人' }}
                </ElButton>
                <ElButton
                  v-if="batch.qcWorkerId"
                  v-permission="'task:complete'"
                  type="primary"
                  size="small"
                  @click="openInspection(batch)"
                >
                  质检完成，录入结果
                </ElButton>
              </div>
            </article>
            <ElEmpty
              v-if="externalPendingQc.length === 0"
              description="暂无其他部门的待质检批次"
            />
          </div>
        </div>

        <div class="panel-block">
          <div class="block-heading">
            <h3>正式归属 QC 的产品</h3>
            <span>{{ officialQcProducts.length }} 个产品</span>
          </div>
          <div class="official-products">
            <div
              v-for="product in officialQcProducts"
              :key="product.id"
              class="official-product"
            >
              <span>订单 {{ product.orderId }} · {{ product.zzCode }}</span>
              <strong>{{ product.productName }}</strong>
              <em>数量 {{ product.quantity }}</em>
              <ElButton
                v-if="productProcesses(product.id).length === 0"
                v-permission="'task:assign'"
                size="small"
                @click="configureOfficialQc(product)"
              >
                配置终检
              </ElButton>
              <div
                v-for="process in productProcesses(product.id)"
                :key="process.id"
                class="official-process"
              >
                <span>{{ process.processName }} · 可开单 {{ process.availableQuantity }}</span>
                <ElButton
                  v-permission="'task:assign'"
                  size="small"
                  type="primary"
                  :disabled="process.availableQuantity <= 0 || workers.length === 0"
                  @click="openOfficialWorkOrder(product, process)"
                >
                  开 QC 工单
                </ElButton>
              </div>
            </div>
            <ElEmpty
              v-if="officialQcProducts.length === 0"
              description="暂无正式 QC 库存"
            />
          </div>
        </div>
      </section>

      <section class="section-card order-panel">
        <h2>QC 部门工单</h2>
        <div class="official-orders">
          <article v-for="item in workOrders" :key="item.id" class="official-order">
            <div>
              <span>{{ item.workOrderNo }} · {{ item.productName }} · {{ item.workerName }}</span>
              <strong>{{ item.processName }}</strong>
              <em>
                领取 {{ item.issuedQuantity }} / 加工中 {{ item.processingQuantity }} /
                OK {{ item.okQuantity }} / 报废 {{ item.scrapQuantity }} / 遗失
                {{ item.lostQuantity }}
              </em>
            </div>
            <ElButton
              v-if="item.status === 'open'"
              v-permission="'task:complete'"
              type="primary"
              size="small"
              @click="openDirectReport(item)"
            >
              报工
            </ElButton>
            <ElTag v-else type="success">已结单</ElTag>
          </article>
          <ElEmpty v-if="workOrders.length === 0" description="暂无 QC 工单" />
        </div>
      </section>
    </div>

    <ElDialog v-model="inspectionDialogVisible" title="录入 QC 结果" width="540px">
      <div class="inspection-summary">
        <strong>{{ activeBatch?.productName }} / {{ activeBatch?.processName }}</strong>
        <span>本次送检：{{ activeBatch?.submittedQuantity }}</span>
      </div>
      <ElAlert
        :title="`质检工人：${activeBatch?.qcWorkerName || '-'}`"
        type="info"
        :closable="false"
        show-icon
      />
      <ElForm label-position="top">
        <div class="quantity-grid">
          <ElFormItem label="OK"><ElInputNumber v-model="form.okQuantity" :min="0" /></ElFormItem>
          <ElFormItem label="返修"><ElInputNumber v-model="form.reworkQuantity" :min="0" /></ElFormItem>
          <ElFormItem label="报废"><ElInputNumber v-model="form.scrapQuantity" :min="0" /></ElFormItem>
          <ElFormItem label="遗失"><ElInputNumber v-model="form.lostQuantity" :min="0" /></ElFormItem>
        </div>
        <ElFormItem label="不良原因">
          <ElInput v-model="form.defectReason" type="textarea" />
        </ElFormItem>
      </ElForm>
      <div :class="['total-check', { invalid: !resultMatches }]">
        结果合计 {{ resultTotal }} / 送检 {{ activeBatch?.submittedQuantity }}
      </div>
      <template #footer>
        <ElButton @click="inspectionDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="!resultMatches" @click="submitInspection">
          确认并永久提交
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="assignmentDialogVisible" title="分配 QC 工人" width="440px">
      <div class="assignment-summary">
        <strong>{{ activeBatch?.productName }} / {{ activeBatch?.processName }}</strong>
        <span>送检数量：{{ activeBatch?.submittedQuantity }}</span>
      </div>
      <ElForm label-position="top">
        <ElFormItem label="QC 工人" required>
          <ElSelect v-model="assignmentWorkerId" placeholder="请选择 QC 工人">
            <ElOption
              v-for="worker in workers"
              :key="worker.id"
              :label="worker.name"
              :value="worker.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="assignmentDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="!assignmentWorkerId" @click="submitAssignment">
          确认分配
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="workerDialogVisible" title="添加 QC 工人" width="420px">
      <ElInput v-model="workerName" placeholder="QC 工人姓名" @keyup.enter="submitWorker" />
      <template #footer>
        <ElButton @click="workerDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="!workerName.trim()" @click="submitWorker">添加</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="workOrderDialogVisible" title="开 QC 工单" width="480px">
      <ElForm label-position="top">
        <ElFormItem label="工艺">
          <strong>{{ activeProcess?.processName }}</strong>
        </ElFormItem>
        <ElFormItem label="QC 工人">
          <ElSelect v-model="workOrderForm.workerId">
            <ElOption
              v-for="worker in workers"
              :key="worker.id"
              :label="worker.name"
              :value="worker.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="领取数量">
          <ElInputNumber
            v-model="workOrderForm.quantity"
            :min="1"
            :max="activeProcess?.availableQuantity || 1"
          />
        </ElFormItem>
        <ElFormItem label="备注">
          <ElInput v-model="workOrderForm.note" type="textarea" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="workOrderDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitOfficialWorkOrder">确认开单</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="directDialogVisible" title="QC 工单报工" width="500px">
      <ElForm label-position="top">
        <ElFormItem label="OK">
          <ElInputNumber v-model="directForm.okQuantity" :min="0" />
        </ElFormItem>
        <ElFormItem label="报废">
          <ElInputNumber v-model="directForm.scrapQuantity" :min="0" />
        </ElFormItem>
        <ElFormItem label="遗失">
          <ElInputNumber v-model="directForm.lostQuantity" :min="0" />
        </ElFormItem>
        <ElFormItem label="原因">
          <ElInput v-model="directForm.reason" type="textarea" />
        </ElFormItem>
      </ElForm>
      <p>本次合计：{{ directTotal }} / 当前加工中：{{ activeWorkOrder?.processingQuantity }}</p>
      <template #footer>
        <ElButton @click="directDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitDirectReport">提交报工</ElButton>
      </template>
    </ElDialog>
  </main>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  padding: 22px;
  background: var(--erp-bg);
}

.dashboard-header,
.section-card,
.submission-card,
.official-product {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 24px;
}

.dashboard-header h1,
.section-card h2 { margin: 6px 0; }
.dashboard-header p { margin: 0; color: var(--erp-text-muted); }
.page-kicker { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.header-actions,
.submission-actions { display: flex; gap: 10px; align-items: center; }
.section-card { margin-bottom: 18px; padding: 18px; }
.workspace-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(420px, 1fr);
  gap: 18px;
  align-items: start;
}
.workspace-layout .section-card { min-width: 0; }
.panel-block + .panel-block {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--erp-border);
}
.block-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.block-heading h3 { margin: 0; font-size: 16px; }
.block-heading span { color: var(--erp-text-muted); font-size: 13px; }
.submission-list,
.official-products,
.official-orders { display: grid; gap: 12px; margin-top: 16px; }
.submission-card { display: flex; justify-content: space-between; gap: 16px; padding: 16px; }
.submission-actions { flex-wrap: wrap; justify-content: flex-end; }
.submission-card > div:first-child,
.official-product { display: grid; gap: 4px; }
.submission-card span,
.submission-card em,
.official-product span,
.official-product em { color: var(--erp-text-muted); font-size: 13px; font-style: normal; }
.official-products { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
.official-product { padding: 14px; }
.official-process,
.official-order {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
}
.official-order > div { display: grid; gap: 4px; }
.official-order span,
.official-order em { color: var(--erp-text-muted); font-size: 13px; font-style: normal; }
.inspection-summary,
.assignment-summary { display: flex; justify-content: space-between; margin-bottom: 16px; }
.inspection-summary + .el-alert { margin-bottom: 16px; }
.quantity-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.total-check { padding: 12px; border-radius: 8px; background: #ecfdf5; color: var(--erp-success); font-weight: 700; }
.total-check.invalid { background: #fef2f2; color: var(--erp-danger); }

@media (max-width: 1100px) {
  .workspace-layout { grid-template-columns: 1fr; }
}

@media (max-width: 760px) {
  .dashboard-header,
  .submission-card { flex-direction: column; }
  .submission-actions { justify-content: flex-start; }
  .quantity-grid { grid-template-columns: 1fr; }
}
</style>
