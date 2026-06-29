<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useProductsStore } from '@/stores/products'
import { useWorkOrdersStore } from '@/stores/workOrders'
import type {
  PolishProcessStep,
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
const { loading, presets, processes, workers, workOrders } = storeToRefs(workOrdersStore)

const configDialogVisible = ref(false)
const workOrderDialogVisible = ref(false)
const workerDialogVisible = ref(false)
const submissionDialogVisible = ref(false)
const directDialogVisible = ref(false)
const cleaningDialogVisible = ref(false)
const presetDialogVisible = ref(false)
const activeProduct = ref<ProductItem | null>(null)
const activeProcess = ref<PolishProcessStep | null>(null)
const activeWorkOrder = ref<WorkOrderItem | null>(null)
const selectedProductId = ref<number | null>(null)
const workerName = ref('')
const submissionQuantity = ref(1)
const cleaningQuantity = ref(1)
const selectedPresetId = ref<number | undefined>()
const editingPresetId = ref<number | undefined>()
const presetName = ref('')
const presetActive = ref(true)
const presetSteps = ref<ProcessStepPayload[]>([])

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
  selectedPresetId.value = undefined
  processSteps.value = existing.length
    ? existing.map((item) => ({
        processName: item.processName,
        requiresCleaning: item.requiresCleaning,
        requiresQc: item.requiresQc,
      }))
    : [
        { processName: '粗光', requiresCleaning: false, requiresQc: true },
        { processName: '全光', requiresCleaning: false, requiresQc: false },
      ]
  configDialogVisible.value = true
}

function applyPreset() {
  const preset = presets.value.find((item) => item.id === selectedPresetId.value)
  if (!preset) return
  processSteps.value = preset.steps.map((step) => ({ ...step }))
}

function addProcessStep() {
  processSteps.value.push({
    processName: '',
    requiresCleaning: false,
    requiresQc: false,
  })
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
      selectedPresetId.value,
    )
    configDialogVisible.value = false
    ElMessage.success('工艺配置已保存')
  } catch {
    ElMessage.error('工艺配置失败，请确认产品尚未开工单')
  }
}

function openWorkOrder(product: ProductItem, process: PolishProcessStep) {
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
      department,
      processName: activeProcess.value.processName,
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
  const available = item.requiresCleaning ? item.cleanedReadyQuantity : item.processingQuantity
  submissionQuantity.value = available > 0 ? 1 : 0
  submissionDialogVisible.value = true
}

function openCleaning(item: WorkOrderItem) {
  activeWorkOrder.value = item
  cleaningQuantity.value = item.processingQuantity > 0 ? 1 : 0
  cleaningDialogVisible.value = true
}

async function submitCleaning() {
  if (!activeWorkOrder.value) return
  try {
    await workOrdersStore.submitToCleaning(
      department,
      activeWorkOrder.value.id,
      cleaningQuantity.value,
    )
    cleaningDialogVisible.value = false
    ElMessage.success('已送去清洗')
  } catch {
    ElMessage.error('送洗失败，请检查加工中数量')
  }
}

async function completeCleaning(cleaningBatchId: number) {
  try {
    await workOrdersStore.completeCleaning(department, cleaningBatchId)
    ElMessage.success('清洗完成')
  } catch {
    ElMessage.error('确认清洗完成失败')
  }
}

function newPreset() {
  editingPresetId.value = undefined
  presetName.value = ''
  presetActive.value = true
  presetSteps.value = [{ processName: '', requiresCleaning: false, requiresQc: false }]
  presetDialogVisible.value = true
}

function editPreset(presetId: number) {
  const preset = presets.value.find((item) => item.id === presetId)
  if (!preset) return
  editingPresetId.value = preset.id
  presetName.value = preset.presetName
  presetActive.value = preset.active
  presetSteps.value = preset.steps.map((step) => ({ ...step }))
  presetDialogVisible.value = true
}

async function submitPreset() {
  if (!presetName.value.trim() || presetSteps.value.some((step) => !step.processName.trim())) {
    ElMessage.warning('请完整填写预设名称和工艺')
    return
  }
  try {
    await workOrdersStore.savePreset(
      presetName.value,
      presetSteps.value,
      presetActive.value,
      editingPresetId.value,
    )
    presetDialogVisible.value = false
    ElMessage.success('工艺预设已保存')
  } catch {
    ElMessage.error('工艺预设保存失败')
  }
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
    await productsStore.loadProducts(department)
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
    productsStore.loadProducts(department),
    workOrdersStore.loadDepartment(department),
    workOrdersStore.loadPresets(),
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
        <ElButton @click="router.push('/dashboard/polish/workers')">工人总览</ElButton>
        <ElButton v-permission="'task:assign'" @click="workerDialogVisible = true">
          添加工人
        </ElButton>
        <ElButton v-permission="'task:assign'" @click="newPreset">工艺预设</ElButton>
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
                :key="process.processName"
                class="process-row"
              >
                <div>
                  <strong>{{ process.sequenceNo }}. {{ process.processName }}</strong>
                  <span>
                    {{ process.requiresCleaning ? '需要清洗' : '无需清洗' }} ·
                    {{ process.requiresQc ? '需要 QC' : '无需 QC' }}
                  </span>
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
                    : item.cleaningQuantity > 0
                      ? `${item.processName}清洗中`
                      : item.cleanedReadyQuantity > 0
                        ? `${item.processName}清洗完成`
                        : `${item.processName}加工中`
                }}
              </ElTag>
            </div>

            <div class="metrics">
              <div><span>领料数</span><strong>{{ item.issuedQuantity }}</strong></div>
              <div><span>加工中</span><strong>{{ item.processingQuantity }}</strong></div>
              <div><span>清洗中</span><strong>{{ item.cleaningQuantity }}</strong></div>
              <div><span>清洗完成</span><strong>{{ item.cleanedReadyQuantity }}</strong></div>
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
                v-if="item.requiresCleaning"
                v-permission="'task:complete'"
                type="primary"
                plain
                size="small"
                :disabled="item.processingQuantity <= 0"
                @click="openCleaning(item)"
              >
                送去清洗
              </ElButton>
              <ElButton
                v-if="item.requiresQc"
                v-permission="'task:complete'"
                type="primary"
                size="small"
                :disabled="(item.requiresCleaning ? item.cleanedReadyQuantity : item.processingQuantity) <= 0"
                @click="openSubmission(item)"
              >
                送 QC
              </ElButton>
              <ElButton
                v-else
                v-permission="'task:complete'"
                type="primary"
                size="small"
                :disabled="(item.requiresCleaning ? item.cleanedReadyQuantity : item.processingQuantity) <= 0"
                @click="openDirectReport(item)"
              >
                直接报工
              </ElButton>
            </div>

            <div v-if="item.cleaningBatches.length" class="batch-list">
              <div
                v-for="batch in item.cleaningBatches"
                :key="`cleaning-${batch.id}`"
                class="batch-row"
              >
                <span>第 {{ batch.batchNo }} 批清洗 · {{ batch.quantity }} · {{ batch.sentAt }}</span>
                <ElButton
                  v-if="batch.status === 'cleaning'"
                  v-permission="'task:complete'"
                  size="small"
                  type="success"
                  @click="completeCleaning(batch.id)"
                >
                  清洗完成
                </ElButton>
                <span v-else>已完成 · {{ batch.completedAt }}</span>
              </div>
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

    <ElDialog v-model="configDialogVisible" title="配置磨房工艺" width="820px">
      <div class="form-stack">
        <div class="preset-picker">
          <ElSelect v-model="selectedPresetId" clearable placeholder="选择工艺预设">
            <ElOption
              v-for="preset in presets.filter((item) => item.active)"
              :key="preset.id"
              :label="preset.presetName"
              :value="preset.id"
            />
          </ElSelect>
          <ElButton :disabled="!selectedPresetId" @click="applyPreset">应用预设</ElButton>
        </div>
        <div v-for="(step, index) in processSteps" :key="index" class="config-row">
          <span>{{ index + 1 }}</span>
          <ElInput v-model="step.processName" placeholder="工艺名称" />
          <div class="config-choice">
            <label>是否清洗</label>
            <ElRadioGroup v-model="step.requiresCleaning">
              <ElRadio :value="true">是</ElRadio>
              <ElRadio :value="false">否</ElRadio>
            </ElRadioGroup>
          </div>
          <div class="config-choice">
            <label>是否 QC</label>
            <ElRadioGroup v-model="step.requiresQc">
              <ElRadio :value="true">是</ElRadio>
              <ElRadio :value="false">否</ElRadio>
            </ElRadioGroup>
          </div>
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
      <p>
        当前可送检：{{ activeWorkOrder?.requiresCleaning
          ? activeWorkOrder?.cleanedReadyQuantity
          : activeWorkOrder?.processingQuantity }}
      </p>
      <ElInputNumber
        v-model="submissionQuantity"
        :min="1"
        :max="(activeWorkOrder?.requiresCleaning
          ? activeWorkOrder?.cleanedReadyQuantity
          : activeWorkOrder?.processingQuantity) || 1"
      />
      <template #footer>
        <ElButton @click="submissionDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitToQc">确认送检</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="cleaningDialogVisible" title="送去清洗" width="440px">
      <p>当前加工中：{{ activeWorkOrder?.processingQuantity }}</p>
      <ElInputNumber
        v-model="cleaningQuantity"
        :min="1"
        :max="activeWorkOrder?.processingQuantity || 1"
      />
      <template #footer>
        <ElButton @click="cleaningDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitCleaning">确认送洗</ElButton>
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
      <p>
        本次合计：{{ directTotal }} / 当前可报工：{{ activeWorkOrder?.requiresCleaning
          ? activeWorkOrder?.cleanedReadyQuantity
          : activeWorkOrder?.processingQuantity }}
      </p>
      <template #footer>
        <ElButton @click="directDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitDirectReport">提交报工</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="presetDialogVisible" title="磨房工艺预设" width="820px">
      <div class="preset-list">
        <div v-for="preset in presets" :key="preset.id" class="preset-row">
          <span>{{ preset.presetName }} · {{ preset.processFlow.join(' → ') }}</span>
          <div>
            <ElTag :type="preset.active ? 'success' : 'info'">
              {{ preset.active ? '启用' : '停用' }}
            </ElTag>
            <ElButton text @click="editPreset(preset.id)">编辑</ElButton>
          </div>
        </div>
      </div>
      <ElDivider />
      <ElForm label-position="top">
        <ElFormItem label="预设名称" required>
          <ElInput v-model="presetName" />
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSwitch v-model="presetActive" active-text="启用" inactive-text="停用" />
        </ElFormItem>
      </ElForm>
      <div class="form-stack">
        <div v-for="(step, index) in presetSteps" :key="index" class="config-row">
          <span>{{ index + 1 }}</span>
          <ElInput v-model="step.processName" placeholder="工艺名称" />
          <div class="config-choice">
            <label>是否清洗</label>
            <ElRadioGroup v-model="step.requiresCleaning">
              <ElRadio :value="true">是</ElRadio>
              <ElRadio :value="false">否</ElRadio>
            </ElRadioGroup>
          </div>
          <div class="config-choice">
            <label>是否 QC</label>
            <ElRadioGroup v-model="step.requiresQc">
              <ElRadio :value="true">是</ElRadio>
              <ElRadio :value="false">否</ElRadio>
            </ElRadioGroup>
          </div>
          <ElButton type="danger" text @click="presetSteps.splice(index, 1)">删除</ElButton>
        </div>
        <ElButton
          @click="presetSteps.push({ processName: '', requiresCleaning: false, requiresQc: false })"
        >
          添加工艺
        </ElButton>
      </div>
      <template #footer>
        <ElButton @click="newPreset">新建预设</ElButton>
        <ElButton @click="presetDialogVisible = false">关闭</ElButton>
        <ElButton type="primary" @click="submitPreset">保存预设</ElButton>
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
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(90px, 1fr)); gap: 8px; margin: 14px 0; }
.metrics div { padding: 9px; border-radius: 8px; background: var(--erp-surface-muted); }
.metrics span { display: block; color: var(--erp-text-muted); font-size: 12px; }
.metrics strong { display: block; margin-top: 3px; }
.batch-list { margin-top: 12px; }
.batch-row { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; }
.config-row {
  display: grid;
  grid-template-columns: 30px minmax(160px, 1fr) 150px 150px auto;
  gap: 12px;
  align-items: center;
}
.config-choice { display: grid; gap: 6px; }
.config-choice label { color: var(--erp-text-muted); font-size: 12px; }
.preset-picker { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; }
.preset-list { display: grid; gap: 8px; }
.preset-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
}
.preset-row > div { display: flex; gap: 8px; align-items: center; }

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
