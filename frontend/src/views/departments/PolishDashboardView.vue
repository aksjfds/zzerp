<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useProductsStore } from '@/stores/products'
import { useWorkOrdersStore } from '@/stores/workOrders'
import type {
  DepartmentProcessItem,
  DirectReportPayload,
  ProcessStepPayload,
  ProductItem,
  WorkOrderItem,
} from '@/types/production'

const department = 'polish' as const
const router = useRouter()
const authStore = useAuthStore()
const productsStore = useProductsStore()
const workOrdersStore = useWorkOrdersStore()
const { products } = storeToRefs(productsStore)
const { loading, processes, workers, workOrders } = storeToRefs(workOrdersStore)

const configDialogVisible = ref(false)
const workOrderDialogVisible = ref(false)
const workerDialogVisible = ref(false)
const submissionDialogVisible = ref(false)
const directDialogVisible = ref(false)
const activeProduct = ref<ProductItem | null>(null)
const activeProcess = ref<DepartmentProcessItem | null>(null)
const activeWorkOrder = ref<WorkOrderItem | null>(null)
const selectedProductId = ref<number | null>(null)
const workerName = ref('')
const submissionQuantity = ref(1)

const processSteps = ref<ProcessStepPayload[]>([])
const workOrderForm = reactive({ workerId: 0, quantity: 1, note: '' })
const directForm = reactive<DirectReportPayload>({
  okQuantity: 0,
  scrapQuantity: 0,
  lostQuantity: 0,
  reason: '',
})

const directTotal = computed(
  () => directForm.okQuantity + directForm.scrapQuantity + directForm.lostQuantity,
)

const selectedProduct = computed(
  () => products.value.find((product) => product.id === selectedProductId.value) ?? null,
)

const visibleWorkOrders = computed(() => {
  if (selectedProductId.value === null) return []
  return workOrders.value.filter((item) => item.productId === selectedProductId.value)
})

function selectProduct(product: ProductItem) {
  selectedProductId.value = product.id
}

function productProcesses(productId: number) {
  return processes.value.filter((item) => item.productId === productId)
}

function getDepartmentQuantity(product: ProductItem) {
  return product.repositories
    .filter((repository) => repository.department === department)
    .reduce((total, repository) => total + repository.quantity, 0)
}

function openConfig(product: ProductItem) {
  selectProduct(product)
  activeProduct.value = product
  const existing = productProcesses(product.id)
  processSteps.value = existing.length
    ? existing.map((item) => ({
        processName: item.processName,
        requiresQc: item.requiresQc,
      }))
    : [
        { processName: '粗光', requiresQc: true },
        { processName: '全光', requiresQc: false },
      ]
  configDialogVisible.value = true
}

function addProcessStep() {
  processSteps.value.push({ processName: '', requiresQc: false })
}

function removeProcessStep(index: number) {
  processSteps.value.splice(index, 1)
}

async function submitProcesses() {
  if (!activeProduct.value || processSteps.value.some((item) => !item.processName.trim())) {
    ElMessage.warning('请完整填写工艺名称')
    return
  }
  try {
    await workOrdersStore.configureProcesses(
      department,
      activeProduct.value.id,
      processSteps.value,
    )
    configDialogVisible.value = false
    ElMessage.success('工艺配置已保存')
  } catch {
    ElMessage.error('工艺配置失败，请确认产品尚未开工单')
  }
}

function openWorkOrder(product: ProductItem, process: DepartmentProcessItem) {
  selectProduct(product)
  activeProduct.value = product
  activeProcess.value = process
  workOrderForm.workerId = workers.value[0]?.id ?? 0
  workOrderForm.quantity = process.availableQuantity > 0 ? 1 : 0
  workOrderForm.note = ''
  workOrderDialogVisible.value = true
}

async function submitWorkOrder() {
  if (!activeProduct.value || !activeProcess.value || !workOrderForm.workerId) {
    ElMessage.warning('请选择工人')
    return
  }
  try {
    await workOrdersStore.addWorkOrder(department, {
      productId: activeProduct.value.id,
      processId: activeProcess.value.id,
      workerId: workOrderForm.workerId,
      quantity: workOrderForm.quantity,
      note: workOrderForm.note,
    })
    workOrderDialogVisible.value = false
    ElMessage.success('工单已创建')
  } catch {
    ElMessage.error('工单创建失败，请检查可开单数量')
  }
}

async function submitWorker() {
  if (!workerName.value.trim()) {
    return
  }
  try {
    await workOrdersStore.addWorker(department, workerName.value)
    workerName.value = ''
    workerDialogVisible.value = false
    ElMessage.success('工人已添加')
  } catch {
    ElMessage.error('添加工人失败')
  }
}

function openSubmission(item: WorkOrderItem) {
  activeWorkOrder.value = item
  submissionQuantity.value = item.processingQuantity > 0 ? 1 : 0
  submissionDialogVisible.value = true
}

async function submitToQc() {
  if (!activeWorkOrder.value) {
    return
  }
  try {
    await workOrdersStore.submitToQc(
      department,
      activeWorkOrder.value.id,
      submissionQuantity.value,
    )
    submissionDialogVisible.value = false
    ElMessage.success('已送往 QC')
  } catch {
    ElMessage.error('送检失败，请检查加工中数量')
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
    await workOrdersStore.reportDirect(
      department,
      activeWorkOrder.value.id,
      directForm,
    )
    directDialogVisible.value = false
    await productsStore.loadProducts()
    ElMessage.success('报工已提交')
  } catch {
    ElMessage.error('报工失败，请检查加工中数量')
  }
}

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}

async function loadDashboard() {
  await Promise.all([
    productsStore.loadProducts(),
    workOrdersStore.loadDepartment(department),
  ])

  if (!products.value.some((product) => product.id === selectedProductId.value)) {
    selectedProductId.value = products.value[0]?.id ?? null
  }
}

onMounted(loadDashboard)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div class="navbar-title">
        <div class="page-kicker">磨房部门</div>
        <h1>磨房工单</h1>
      </div>
      <nav class="header-actions" aria-label="磨房导航">
        <ElButton @click="router.push('/dashboard')">产品总览</ElButton>
        <ElButton class="nav-current" type="primary" aria-current="page">磨房工单</ElButton>
        <ElButton v-permission="'task:assign'" @click="workerDialogVisible = true">
          添加工人
        </ElButton>
        <ElButton @click="switchUser">切换用户</ElButton>
      </nav>
    </header>

    <div v-loading="loading" class="workspace-layout">
      <section class="section-card product-panel">
        <div class="section-head">
          <div>
            <h2>磨房产品与工艺</h2>
            <p>内部送检期间，产品正式归属仍为磨房。</p>
          </div>
        </div>

        <div class="product-grid">
          <article
            v-for="product in products"
            :key="product.id"
            :class="['product-card', { selected: product.id === selectedProductId }]"
            role="button"
            tabindex="0"
            @click="selectProduct(product)"
            @keydown.enter="selectProduct(product)"
            @keydown.space.prevent="selectProduct(product)"
          >
            <div class="product-title">
              <div>
                <span>订单 {{ product.orderId }} · {{ product.zzCode }}</span>
                <strong>{{ product.productName }}</strong>
                <em>
                  磨房库存：{{ getDepartmentQuantity(product) }} · 交期：{{ product.deliveryDate }}
                </em>
              </div>
              <ElButton size="small" @click.stop="openConfig(product)">配置工艺</ElButton>
            </div>

            <div v-if="productProcesses(product.id).length" class="process-list">
              <div
                v-for="process in productProcesses(product.id)"
                :key="process.id"
                class="process-row"
              >
                <div>
                  <strong>{{ process.sequenceNo }}. {{ process.processName }}</strong>
                  <span>{{ process.requiresQc ? '需要 QC' : '无需 QC' }}</span>
                </div>
                <div class="process-actions">
                  <em>可开单 {{ process.availableQuantity }}</em>
                  <ElButton
                    v-permission="'task:assign'"
                    size="small"
                    type="primary"
                    :disabled="process.availableQuantity <= 0 || workers.length === 0"
                    @click.stop="openWorkOrder(product, process)"
                  >
                    开工单
                  </ElButton>
                </div>
              </div>
            </div>
            <ElEmpty v-else description="尚未配置磨房工艺" :image-size="56" />
          </article>
          <ElEmpty v-if="products.length === 0" description="暂无磨房产品" />
        </div>
      </section>

      <section class="section-card order-panel">
        <div class="section-head">
          <div>
            <h2>
              工单记录
              <template v-if="selectedProduct">· {{ selectedProduct.productName }}</template>
            </h2>
            <p>加工中数量自动包含 QC 返回的返修数量。</p>
          </div>
        </div>

        <div class="order-list">
          <article v-for="item in visibleWorkOrders" :key="item.id" class="order-card">
            <div class="order-head">
              <div>
                <span>{{ item.workOrderNo }} · {{ item.processName }}</span>
                <strong>{{ item.productName }} / {{ item.workerName }}</strong>
              </div>
              <ElTag :type="item.status === 'closed' ? 'success' : 'warning'">
                {{
                  item.status === 'closed'
                    ? '已结单'
                    : item.pendingQcQuantity > 0
                      ? `${item.processName}质检中`
                      : `${item.processName}加工中`
                }}
              </ElTag>
            </div>

            <div class="metrics">
              <div><span>领料数</span><strong>{{ item.issuedQuantity }}</strong></div>
              <div><span>加工中</span><strong>{{ item.processingQuantity }}</strong></div>
              <div><span>质检中</span><strong>{{ item.pendingQcQuantity }}</strong></div>
              <div><span>累计 OK</span><strong>{{ item.okQuantity }}</strong></div>
              <div><span>累计返修</span><strong>{{ item.reworkQuantity }}</strong></div>
              <div>
                <span>报废 / 遗失</span>
                <strong>{{ item.scrapQuantity }} / {{ item.lostQuantity }}</strong>
              </div>
            </div>

            <div v-if="item.status === 'open'" class="order-actions">
              <ElButton
                v-if="item.requiresQc"
                v-permission="'task:complete'"
                type="primary"
                size="small"
                :disabled="item.processingQuantity <= 0"
                @click="openSubmission(item)"
              >
                送 QC
              </ElButton>
              <ElButton
                v-else
                v-permission="'task:complete'"
                type="primary"
                size="small"
                :disabled="item.processingQuantity <= 0"
                @click="openDirectReport(item)"
              >
                直接报工
              </ElButton>
            </div>

            <div v-if="item.batches.length" class="batch-list">
              <div v-for="batch in item.batches" :key="batch.id" class="batch-row">
                <span>第 {{ batch.batchNo }} 批 · 送检/报工 {{ batch.submittedQuantity }}</span>
                <span v-if="batch.status === 'pending_qc'">等待 QC</span>
                <span v-else>
                  OK {{ batch.okQuantity }} / 返修 {{ batch.reworkQuantity }} /
                  报废 {{ batch.scrapQuantity }} / 遗失 {{ batch.lostQuantity }}
                  <template v-if="batch.qcWorkerName">
                    · QC {{ batch.qcWorkerName }} · {{ batch.inspectedAt }}
                  </template>
                </span>
              </div>
            </div>
          </article>
          <ElEmpty v-if="!selectedProduct" description="请先选择左侧产品" />
          <ElEmpty
            v-else-if="visibleWorkOrders.length === 0"
            description="该产品暂无工单"
          />
        </div>
      </section>
    </div>

    <ElDialog v-model="configDialogVisible" title="配置磨房工艺" width="620px">
      <div class="form-stack">
        <div v-for="(step, index) in processSteps" :key="index" class="config-row">
          <span>{{ index + 1 }}</span>
          <ElInput v-model="step.processName" placeholder="工艺名称" />
          <ElSelect v-model="step.requiresQc">
            <ElOption label="需要 QC" :value="true" />
            <ElOption label="无需 QC" :value="false" />
          </ElSelect>
          <ElButton type="danger" text @click="removeProcessStep(index)">删除</ElButton>
        </div>
        <ElButton @click="addProcessStep">添加工艺</ElButton>
      </div>
      <template #footer>
        <ElButton @click="configDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="processSteps.length === 0" @click="submitProcesses">
          保存
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="workOrderDialogVisible" title="开工单" width="500px">
      <ElForm label-position="top">
        <ElFormItem label="工艺"><strong>{{ activeProcess?.processName }}</strong></ElFormItem>
        <ElFormItem label="工人">
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
        <ElButton type="primary" @click="submitWorkOrder">确认开单</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="workerDialogVisible" title="添加磨房工人" width="420px">
      <ElInput v-model="workerName" placeholder="工人姓名" @keyup.enter="submitWorker" />
      <template #footer>
        <ElButton @click="workerDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="!workerName.trim()" @click="submitWorker">添加</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="submissionDialogVisible" title="送 QC" width="440px">
      <p>当前加工中：{{ activeWorkOrder?.processingQuantity }}</p>
      <ElInputNumber
        v-model="submissionQuantity"
        :min="1"
        :max="activeWorkOrder?.processingQuantity || 1"
      />
      <template #footer>
        <ElButton @click="submissionDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitToQc">确认送检</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="directDialogVisible" title="直接报工" width="500px">
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
.product-card,
.order-card {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 16px 20px;
}

.dashboard-header h1,
.section-head h2 { margin: 6px 0; }
.navbar-title h1 { margin-bottom: 0; font-size: 22px; }
.dashboard-header p,
.section-head p { margin: 0; color: var(--erp-text-muted); }
.page-kicker { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.header-actions,
.order-actions,
.process-actions { display: flex; align-items: center; gap: 8px; }
.header-actions { flex-wrap: wrap; justify-content: flex-end; }
.header-actions :deep(.el-button + .el-button) { margin-left: 0; }
.nav-current { pointer-events: none; }
.section-card { margin-bottom: 18px; padding: 18px; }
.section-head { margin-bottom: 16px; }
.workspace-layout {
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(0, 1.6fr);
  gap: 18px;
  align-items: start;
}
.workspace-layout .section-card { min-width: 0; }
.product-grid,
.order-list,
.process-list,
.batch-list,
.form-stack { display: grid; gap: 12px; }
.product-grid { grid-template-columns: 1fr; }
.product-card,
.order-card { padding: 16px; }
.product-card {
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}
.product-card:hover,
.product-card:focus-visible { border-color: var(--erp-primary); outline: none; }
.product-card.selected {
  border-color: var(--erp-primary);
  background: #eff6ff;
  box-shadow: 0 0 0 2px rgb(37 99 235 / 18%);
}
.product-title,
.order-head,
.process-row { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.product-title div,
.order-head div { display: grid; gap: 4px; }
.product-title span,
.order-head span,
.product-title em,
.process-row span,
.process-actions em { color: var(--erp-text-muted); font-size: 13px; font-style: normal; }
.process-list { margin-top: 14px; }
.process-row,
.batch-row {
  padding: 10px 12px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: var(--erp-surface-muted);
}
.process-row > div:first-child { display: grid; gap: 4px; }
.metrics { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; margin: 14px 0; }
.metrics div { padding: 9px; border-radius: 8px; background: var(--erp-surface-muted); }
.metrics span { display: block; color: var(--erp-text-muted); font-size: 12px; }
.metrics strong { display: block; margin-top: 3px; }
.batch-list { margin-top: 12px; }
.batch-row { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; }
.config-row { display: grid; grid-template-columns: 30px minmax(0, 1fr) 140px auto; gap: 8px; align-items: center; }

@media (max-width: 900px) {
  .dashboard-header,
  .product-title,
  .order-head { flex-direction: column; }
  .dashboard-header { align-items: flex-start; }
  .header-actions { justify-content: flex-start; width: 100%; }
  .workspace-layout { grid-template-columns: 1fr; }
  .metrics { grid-template-columns: 1fr 1fr; }
  .config-row { grid-template-columns: 1fr; }
}
</style>
