<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useProductsStore } from '@/stores/products'
import {
  DEPARTMENT_LABELS,
  DEPARTMENTS,
  type CreateProductPayload,
  type Department,
  type ProductItem,
} from '@/types/production'

const router = useRouter()
const authStore = useAuthStore()
const productsStore = useProductsStore()
const {
  departmentProgress,
  loading: productsLoading,
  products,
  progressLoading,
} = storeToRefs(productsStore)

const productDialogVisible = ref(false)
const progressDialogVisible = ref(false)
const activeProduct = ref<ProductItem | null>(null)
const activeDepartment = ref<Department | null>(null)
const selectedProcessDepartment = ref<Department>('laser')
const searchKeyword = ref('')
const departmentFilter = ref<Department | ''>('')
const deliveryDateRange = ref<string[]>([])
const overdueFilter = ref<'all' | 'yes' | 'no'>('all')
const stockFilter = ref<'all' | 'yes' | 'no'>('all')

const productForm = reactive<CreateProductPayload>({
  orderId: '',
  zzCode: '',
  productName: '',
  deliveryDate: '',
  process: ['polish'],
  quantity: 1,
})

const processOptions = computed(() =>
  DEPARTMENTS.filter(
    (department) => department !== 'in' && department !== 'out' && department !== 'qc',
  ),
)
const productDepartmentOptions = computed(() =>
  DEPARTMENTS.filter((department) => department !== 'in' && department !== 'qc'),
)
const selectableProcessOptions = computed(() =>
  processOptions.value.filter((department) => !productForm.process.includes(department)),
)
const canSubmitProduct = computed(() =>
  Boolean(
    productForm.orderId.trim()
    && productForm.zzCode.trim()
    && productForm.productName.trim()
    && productForm.deliveryDate
    && productForm.process.length > 0,
  ),
)
const isAdmin = computed(
  () => authStore.user?.department === 'sys' && authStore.hasPermission('product:add'),
)
const departmentDashboardPath = computed(() => {
  const department = authStore.department
  return department && department !== 'sys' ? `/dashboard/${department}` : null
})
const currentDepartmentName = computed(() => {
  const department = authStore.department
  if (!department) return '公开页面'
  if (department === 'sys') return '系统管理'
  return `${DEPARTMENT_LABELS[department]}部门`
})
const activeProgressTitle = computed(() => {
  if (!activeProduct.value) {
    return ''
  }

  const departmentName = activeDepartment.value ? getDepartmentLabel(activeDepartment.value) : ''
  return [
    activeProduct.value.orderId,
    activeProduct.value.productName,
    `${departmentName}工艺进度`,
  ].join(' / ')
})
const today = (() => {
  const date = new Date()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
})()
const filteredProducts = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()
  const [startDate, endDate] = deliveryDateRange.value

  return products.value.filter((product) => {
    const matchesKeyword = !keyword || [product.orderId, product.zzCode, product.productName]
      .some((value) => value.toLowerCase().includes(keyword))
    const matchesDepartment = !departmentFilter.value
      || getDepartmentQuantity(product, departmentFilter.value) > 0
    const matchesDate = (!startDate || product.deliveryDate >= startDate)
      && (!endDate || product.deliveryDate <= endDate)
    const overdue = product.deliveryDate < today
    const matchesOverdue = overdueFilter.value === 'all'
      || (overdueFilter.value === 'yes' ? overdue : !overdue)
    const hasProductionStock = product.repositories.some(
      (repository) => repository.department !== 'out' && repository.quantity > 0,
    )
    const matchesStock = stockFilter.value === 'all'
      || (stockFilter.value === 'yes' ? hasProductionStock : !hasProductionStock)

    return matchesKeyword
      && matchesDepartment
      && matchesDate
      && matchesOverdue
      && matchesStock
  })
})
function getDepartmentLabel(department: Department) {
  return DEPARTMENT_LABELS[department]
}

function getDisplayDepartments(product: ProductItem) {
  return [...product.process.filter((department) => department !== 'qc'), 'out'] as Department[]
}

function getDepartmentQuantity(product: ProductItem, department: Department) {
  return product.repositories
    .filter((repository) => repository.department === department)
    .reduce((total, repository) => total + repository.quantity, 0)
}

function resetProductForm() {
  productForm.orderId = ''
  productForm.zzCode = ''
  productForm.productName = ''
  productForm.deliveryDate = ''
  productForm.process = ['polish']
  productForm.quantity = 1
  selectedProcessDepartment.value = selectableProcessOptions.value[0] ?? 'laser'
}

function openProductDialog() {
  resetProductForm()
  productDialogVisible.value = true
}

function addProcessDepartment() {
  if (productForm.process.includes(selectedProcessDepartment.value)) {
    return
  }

  productForm.process.push(selectedProcessDepartment.value)
  selectedProcessDepartment.value = selectableProcessOptions.value[0] ?? 'laser'
}

function removeProcessDepartment(index: number) {
  productForm.process.splice(index, 1)
  selectedProcessDepartment.value = selectableProcessOptions.value[0] ?? 'laser'
}

function moveProcessDepartment(index: number, direction: -1 | 1) {
  const targetIndex = index + direction

  if (targetIndex < 0 || targetIndex >= productForm.process.length) {
    return
  }

  const current = productForm.process[index]
  const target = productForm.process[targetIndex]

  if (!current || !target) {
    return
  }

  productForm.process[index] = target
  productForm.process[targetIndex] = current
}

async function submitProduct() {
  if (!canSubmitProduct.value) {
    return
  }

  await productsStore.createProduct(productForm)
  productDialogVisible.value = false
}

async function openDepartmentProgress(product: ProductItem, department: Department) {
  activeProduct.value = product
  activeDepartment.value = department
  progressDialogVisible.value = true
  try {
    await productsStore.loadDepartmentProgress(product.id, department)
  } catch {
    progressDialogVisible.value = false
    ElMessage.error('部门工艺进度加载失败')
  }
}

function resetFilters() {
  searchKeyword.value = ''
  departmentFilter.value = ''
  deliveryDateRange.value = []
  overdueFilter.value = 'all'
  stockFilter.value = 'all'
}

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}

function goToLogin() {
  router.push('/login')
}

function goToDepartmentDashboard() {
  if (departmentDashboardPath.value) {
    router.push(departmentDashboardPath.value)
  }
}

async function loadDashboard() {
  await productsStore.loadProducts()
}

onMounted(loadDashboard)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div class="navbar-title">
        <div class="page-kicker">{{ currentDepartmentName }}</div>
        <h1>产品流转看板</h1>
      </div>
      <nav class="header-actions" aria-label="产品总览导航">
        <ElButton class="nav-current" type="primary" aria-current="page">产品总览</ElButton>
        <ElButton
          v-if="departmentDashboardPath"
          @click="goToDepartmentDashboard"
        >
          返回{{ currentDepartmentName }}
        </ElButton>
        <ElButton v-if="isAdmin" type="primary" plain @click="openProductDialog">
          新增产品
        </ElButton>
        <ElButton v-if="authStore.isLoggedIn" @click="switchUser">切换用户</ElButton>
        <ElButton v-else @click="goToLogin">登录</ElButton>
      </nav>
    </header>

    <section class="filter-panel">
      <div class="filter-grid">
        <ElInput
          v-model="searchKeyword"
          clearable
          placeholder="搜索订单号、本厂编码或产品名称"
        />
        <ElSelect v-model="departmentFilter" clearable placeholder="所在部门">
          <ElOption
            v-for="department in productDepartmentOptions"
            :key="department"
            :label="getDepartmentLabel(department)"
            :value="department"
          />
        </ElSelect>
        <ElDatePicker
          v-model="deliveryDateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="交期开始"
          end-placeholder="交期结束"
        />
        <ElSelect v-model="overdueFilter" placeholder="是否逾期">
          <ElOption label="全部交期" value="all" />
          <ElOption label="已逾期" value="yes" />
          <ElOption label="未逾期" value="no" />
        </ElSelect>
        <ElSelect v-model="stockFilter" placeholder="生产中库存">
          <ElOption label="全部库存状态" value="all" />
          <ElOption label="还有生产中库存" value="yes" />
          <ElOption label="无生产中库存" value="no" />
        </ElSelect>
        <ElButton @click="resetFilters">重置筛选</ElButton>
      </div>
      <div class="filter-result">共 {{ filteredProducts.length }} 个产品</div>
    </section>

    <section v-loading="productsLoading" class="product-list">
      <article v-for="product in filteredProducts" :key="product.id" class="product-card">
        <div class="product-main">
          <div class="product-code">订单 {{ product.orderId }} · {{ product.zzCode }}</div>
          <h2>{{ product.productName }}</h2>
        </div>
        <div class="product-meta">
          <div>
            <span>交货日期</span>
            <strong>{{ product.deliveryDate }}</strong>
            <ElTag v-if="product.deliveryDate < today" size="small" type="danger">已逾期</ElTag>
          </div>
          <div>
            <span>当前总量</span>
            <strong>{{ product.quantity }}</strong>
          </div>
        </div>
        <div class="department-stock-grid">
          <button
            v-for="department in getDisplayDepartments(product)"
            :key="department"
            type="button"
            class="department-stock"
            @click="openDepartmentProgress(product, department)"
          >
            <span>{{ getDepartmentLabel(department) }}</span>
            <strong>{{ getDepartmentQuantity(product, department) }}</strong>
          </button>
        </div>
      </article>
      <ElEmpty
        v-if="!productsLoading && filteredProducts.length === 0"
        description="没有符合条件的产品"
      />
    </section>

    <ElDialog v-model="progressDialogVisible" :title="activeProgressTitle" width="900px">
      <div v-loading="progressLoading" class="progress-dialog-body">
        <template v-if="departmentProgress">
          <div class="progress-summary">
            <div>
              <span>进入该部门总量</span>
              <strong>{{ departmentProgress.enteredQuantity }}</strong>
            </div>
            <div>
              <span>当前部门库存</span>
              <strong>{{ departmentProgress.currentQuantity }}</strong>
            </div>
          </div>

          <div v-if="departmentProgress.processes.length" class="progress-process-list">
            <article
              v-for="process in departmentProgress.processes"
              :key="process.id"
              class="progress-process-card"
            >
              <div class="progress-process-head">
                <div>
                  <span>第 {{ process.sequenceNo }} 道工艺</span>
                  <strong>{{ process.processName }}</strong>
                </div>
                <ElTag :type="process.requiresQc ? 'warning' : 'info'">
                  {{ process.requiresQc ? '需要 QC' : '无需 QC' }}
                </ElTag>
              </div>
              <ElProgress :percentage="process.progress" :stroke-width="14" />
              <div class="progress-metrics">
                <div><span>待开单</span><strong>{{ process.waitingQuantity }}</strong></div>
                <div><span>累计投入</span><strong>{{ process.issuedQuantity }}</strong></div>
                <div><span>加工中</span><strong>{{ process.processingQuantity }}</strong></div>
                <div><span>清洗中</span><strong>{{ process.cleaningQuantity }}</strong></div>
                <div><span>清洗完成</span><strong>{{ process.cleanedReadyQuantity }}</strong></div>
                <div><span>质检中</span><strong>{{ process.pendingQcQuantity }}</strong></div>
                <div><span>累计 OK</span><strong>{{ process.okQuantity }}</strong></div>
                <div><span>累计返修</span><strong>{{ process.reworkQuantity }}</strong></div>
                <div><span>累计报废</span><strong>{{ process.scrapQuantity }}</strong></div>
                <div><span>累计遗失</span><strong>{{ process.lostQuantity }}</strong></div>
              </div>
            </article>
          </div>
          <ElEmpty v-else description="尚未开始加工" :image-size="72" />
        </template>
      </div>
    </ElDialog>

    <ElDialog v-model="productDialogVisible" title="新增产品" width="620px">
      <ElForm :model="productForm" label-position="top">
        <ElFormItem label="订单号" required>
          <ElInput v-model="productForm.orderId" placeholder="请输入订单号" />
        </ElFormItem>
        <ElFormItem label="本厂编码" required>
          <ElInput v-model="productForm.zzCode" />
        </ElFormItem>
        <ElFormItem label="产品名称" required>
          <ElInput v-model="productForm.productName" />
        </ElFormItem>
        <ElFormItem label="交货日期" required>
          <ElDatePicker
            class="delivery-date-picker"
            v-model="productForm.deliveryDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择交货日期"
          />
        </ElFormItem>
        <ElFormItem label="初始数量">
          <ElInputNumber v-model="productForm.quantity" :min="1" />
        </ElFormItem>
        <ElFormItem label="有序工艺流程">
          <div class="process-builder">
            <div class="process-picker">
              <ElSelect v-model="selectedProcessDepartment" :disabled="selectableProcessOptions.length === 0">
                <ElOption
                  v-for="department in selectableProcessOptions"
                  :key="department"
                  :label="getDepartmentLabel(department)"
                  :value="department"
                />
              </ElSelect>
              <ElButton :disabled="selectableProcessOptions.length === 0" @click="addProcessDepartment">
                加入流程
              </ElButton>
            </div>
            <div class="process-list">
              <div v-for="(department, index) in productForm.process" :key="department" class="process-row">
                <span>{{ index + 1 }}</span>
                <strong>{{ getDepartmentLabel(department) }}</strong>
                <div class="process-actions">
                  <ElButton
                    text
                    :disabled="index === 0"
                    @click="moveProcessDepartment(index, -1)"
                  >
                    上移
                  </ElButton>
                  <ElButton
                    text
                    :disabled="index === productForm.process.length - 1"
                    @click="moveProcessDepartment(index, 1)"
                  >
                    下移
                  </ElButton>
                  <ElButton text type="danger" @click="removeProcessDepartment(index)">移除</ElButton>
                </div>
              </div>
            </div>
          </div>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="productDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="!canSubmitProduct" @click="submitProduct">确认</ElButton>
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
.filter-panel,
.product-card {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #ffffff;
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

.page-kicker,
.product-code {
  color: var(--erp-primary);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.delivery-date-picker {
  width: 100%;
}

.dashboard-header h1 { margin: 6px 0; }

.navbar-title h1 {
  margin-bottom: 0;
  font-size: 22px;
}

.dashboard-header p {
  margin: 0;
  color: var(--erp-text-muted);
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
}

.header-actions :deep(.el-button + .el-button) { margin-left: 0; }
.nav-current { pointer-events: none; }

.filter-panel {
  margin-bottom: 18px;
  padding: 16px;
}

.filter-grid {
  display: grid;
  grid-template-columns: minmax(260px, 1.5fr) minmax(140px, 0.7fr) minmax(300px, 1.2fr) minmax(150px, 0.7fr) minmax(180px, 0.8fr) auto;
  gap: 10px;
  align-items: center;
}

.filter-grid :deep(.el-date-editor) { width: 100%; }
.filter-result { margin-top: 12px; color: var(--erp-text-muted); font-size: 13px; }

.product-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.product-card {
  display: grid;
  grid-template-columns: minmax(220px, 0.8fr) 220px minmax(420px, 1.6fr);
  gap: 20px;
  align-items: center;
  padding: 16px 18px;
}

.product-main h2 { margin: 5px 0 0; font-size: 19px; }
.product-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.product-meta > div { display: grid; gap: 4px; }
.product-meta span { color: var(--erp-text-muted); font-size: 12px; }
.product-meta strong { font-size: 15px; }
.product-meta .el-tag { justify-self: start; }

.progress-dialog-body {
  min-height: 160px;
  max-height: 68vh;
  overflow-y: auto;
  padding-right: 4px;
}

.progress-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.progress-summary > div {
  padding: 14px;
  border-radius: 8px;
  background: var(--erp-surface-muted);
}

.progress-summary span,
.progress-metrics span,
.progress-process-head span { color: var(--erp-text-muted); font-size: 12px; }
.progress-summary strong { display: block; margin-top: 4px; font-size: 22px; }
.progress-process-list { display: grid; gap: 14px; }
.progress-process-card { padding: 16px; border: 1px solid var(--erp-border); border-radius: 8px; }
.progress-process-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.progress-process-head > div { display: grid; gap: 4px; }
.progress-process-head strong { font-size: 17px; }
.progress-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
  gap: 8px;
  margin-top: 14px;
}
.progress-metrics > div { padding: 9px; border-radius: 8px; background: var(--erp-surface-muted); }
.progress-metrics strong { display: block; margin-top: 3px; }

.department-stock-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
  gap: 8px;
}

.department-stock {
  display: grid;
  gap: 4px;
  min-height: 68px;
  padding: 10px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: var(--erp-surface-muted);
  color: var(--erp-text);
  cursor: pointer;
  text-align: left;
}

.department-stock:hover {
  border-color: var(--erp-primary);
  background: #eff6ff;
}

.department-stock span {
  color: var(--erp-text-muted);
  font-size: 13px;
}

.department-stock strong {
  font-size: 24px;
  line-height: 1;
}

.process-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.process-builder {
  display: grid;
  gap: 12px;
  width: 100%;
}

.process-picker {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.process-list {
  display: grid;
  gap: 8px;
}

.process-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: var(--erp-surface-muted);
}

.process-row span {
  display: grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border-radius: 8px;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 700;
}

@media (max-width: 1300px) {
  .filter-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 1100px) {
  .product-card { grid-template-columns: 1fr; }
}

@media (max-width: 900px) {
  .dashboard-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .header-actions {
    justify-content: flex-start;
    width: 100%;
  }

  .filter-grid,
  .product-card {
    grid-template-columns: 1fr;
  }

  .product-meta,
  .progress-summary { grid-template-columns: 1fr 1fr; }

  .progress-metrics { grid-template-columns: 1fr 1fr; }

  .process-row,
  .process-picker {
    grid-template-columns: 1fr;
  }
}
</style>
