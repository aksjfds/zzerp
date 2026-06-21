<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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
const { loading: productsLoading, products, records } = storeToRefs(productsStore)

const productDialogVisible = ref(false)
const recordsDialogVisible = ref(false)
const activeProduct = ref<ProductItem | null>(null)
const activeDepartment = ref<Department | null>(null)
const selectedProcessDepartment = ref<Department>('laser')

const productForm = reactive<CreateProductPayload>({
  zzCode: '',
  productName: '',
  process: ['laser', 'stamp', 'cnc', 'polish', 'qc'],
  quantity: 1,
})

const processOptions = computed(() =>
  DEPARTMENTS.filter((department) => department !== 'in' && department !== 'out'),
)
const selectableProcessOptions = computed(() =>
  processOptions.value.filter((department) => !productForm.process.includes(department)),
)
const activeTimelineTitle = computed(() => {
  if (!activeProduct.value) {
    return ''
  }

  const departmentName = activeDepartment.value ? getDepartmentLabel(activeDepartment.value) : ''
  return `${activeProduct.value.productName} / ${departmentName}流转时间线`
})
function getDepartmentLabel(department: Department) {
  return DEPARTMENT_LABELS[department]
}

function getDisplayDepartments(product: ProductItem) {
  return [...product.process, 'out'] as Department[]
}

function getDepartmentQuantity(product: ProductItem, department: Department) {
  return product.repositories
    .filter((repository) => repository.department === department)
    .reduce((total, repository) => total + repository.quantity, 0)
}

function resetProductForm() {
  productForm.zzCode = ''
  productForm.productName = ''
  productForm.process = ['laser', 'stamp', 'cnc', 'polish', 'qc']
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
  await productsStore.createProduct(productForm)
  productDialogVisible.value = false
}

async function openRecords(product: ProductItem, department?: Department) {
  activeProduct.value = product
  activeDepartment.value = department ?? null
  await productsStore.loadRecords(product.zzCode, product.productName, department)
  recordsDialogVisible.value = true
}

function logout() {
  authStore.logout()
  router.replace('/login')
}

async function loadDashboard() {
  await productsStore.loadProducts()
}

onMounted(loadDashboard)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <div class="page-kicker">Admin Dashboard</div>
        <h1>产品流转看板</h1>
        <p>管理员只能新增产品，并查看产品的流转时间线。</p>
      </div>
      <div class="header-actions">
        <ElButton v-permission="'product:add'" type="primary" @click="openProductDialog">
          新增产品
        </ElButton>
        <ElButton @click="logout">退出</ElButton>
      </div>
    </header>

    <section class="summary-grid">
      <div class="summary-card">
        <span>产品数量</span>
        <strong>{{ products.length }}</strong>
      </div>
    </section>

    <section v-loading="productsLoading" class="product-grid">
      <article v-for="product in products" :key="product.id" class="product-card">
        <div class="product-head">
          <div>
            <div class="product-code">{{ product.zzCode }}</div>
            <h2>{{ product.productName }}</h2>
          </div>
        </div>

        <div class="department-stock-grid">
          <button
            v-for="department in getDisplayDepartments(product)"
            :key="department"
            type="button"
            class="department-stock"
            @click="openRecords(product, department)"
          >
            <span>{{ getDepartmentLabel(department) }}</span>
            <strong>{{ getDepartmentQuantity(product, department) }}</strong>
          </button>
        </div>
      </article>
      <ElEmpty v-if="!productsLoading && products.length === 0" description="暂无产品" />
    </section>

    <ElDialog v-model="recordsDialogVisible" :title="activeTimelineTitle" width="560px">
      <div class="records-dialog-body">
        <div class="records-head">
          <span>流转记录</span>
          <strong>{{ records.length }} 条</strong>
        </div>
        <ElTimeline :reverse="true" v-if="records.length > 0">
          <ElTimelineItem v-for="record in records" :key="record.id" :timestamp="record.createdAt">
            {{ getDepartmentLabel(record.fromRepository) }} -> {{ getDepartmentLabel(record.toRepository) }}
            {{ record.quantity }}
            <span v-if="record.note">，{{ record.note }}</span>
          </ElTimelineItem>
        </ElTimeline>
        <ElEmpty v-else description="暂无流转记录" :image-size="72" />
      </div>
    </ElDialog>

    <ElDialog v-model="productDialogVisible" title="新增产品" width="620px">
      <ElForm :model="productForm" label-position="top">
        <ElFormItem label="本厂编码">
          <ElInput v-model="productForm.zzCode" />
        </ElFormItem>
        <ElFormItem label="产品名称">
          <ElInput v-model="productForm.productName" />
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
                  <ElButton text :disabled="index === 0" @click="moveProcessDepartment(index, -1)">上移</ElButton>
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
        <ElButton type="primary" :disabled="productForm.process.length === 0" @click="submitProduct">确认</ElButton>
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
.summary-card,
.product-card {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--erp-shadow-sm);
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 24px;
}

.page-kicker,
.product-code {
  color: var(--erp-primary);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.dashboard-header h1,
.product-head h2 {
  margin: 6px 0;
}

.dashboard-header p {
  margin: 0;
  color: var(--erp-text-muted);
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.summary-card {
  padding: 18px;
}

.summary-card span {
  color: var(--erp-text-muted);
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  font-size: 26px;
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.product-card {
  padding: 18px;
}

.product-head,
.records-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.records-dialog-body {
  max-height: 520px;
  overflow-y: auto;
  padding-right: 4px;
}

.department-stock-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
  gap: 8px;
  margin-top: 14px;
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

@media (max-width: 900px) {
  .dashboard-header,
  .header-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid,
  .product-grid {
    grid-template-columns: 1fr;
  }

  .process-row,
  .process-picker {
    grid-template-columns: 1fr;
  }
}
</style>
