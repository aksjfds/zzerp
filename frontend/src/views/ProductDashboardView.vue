<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useProductsStore } from '@/stores/products'
import { useTasksStore } from '@/stores/tasks'
import {
  DEPARTMENT_LABELS,
  DEPARTMENTS,
  type CreateProductPayload,
  type CreateTaskPayload,
  type Department,
  type ProductItem,
} from '@/types/production'

const router = useRouter()
const authStore = useAuthStore()
const productsStore = useProductsStore()
const tasksStore = useTasksStore()
const { loading: productsLoading, products, records } = storeToRefs(productsStore)
const { loading: tasksLoading, procedures, tasks, workers } = storeToRefs(tasksStore)

const productDialogVisible = ref(false)
const activeProduct = ref<ProductItem | null>(null)
const selectedProcessDepartment = ref<Department>('laser')

const productForm = reactive<CreateProductPayload>({
  zzCode: '',
  productName: '',
  process: ['laser', 'stamp', 'cnc', 'polish', 'qc'],
  quantity: 1,
})

const taskForm = reactive<CreateTaskPayload>({
  zzCode: '',
  product: '',
  worker: '',
  department: 'laser',
  procedure: '',
  quantity: 1,
  note: '',
})

const isAdmin = computed(() => authStore.department === 'sys')
const currentDepartment = computed<Department | null>(() =>
  authStore.department && authStore.department !== 'sys' ? authStore.department : null,
)
const currentDepartmentName = computed(() =>
  currentDepartment.value ? getDepartmentLabel(currentDepartment.value) : '',
)
const processOptions = computed(() =>
  DEPARTMENTS.filter((department) => department !== 'in' && department !== 'out'),
)
const selectableProcessOptions = computed(() =>
  processOptions.value.filter((department) => !productForm.process.includes(department)),
)
const departmentProducts = computed(() => {
  if (!currentDepartment.value) {
    return []
  }

  return products.value.filter((product) =>
    product.repositories.some(
      (repository) => repository.department === currentDepartment.value && repository.quantity > 0,
    ),
  )
})

function getDepartmentLabel(department: Department) {
  return DEPARTMENT_LABELS[department]
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

async function openRecords(product: ProductItem) {
  activeProduct.value = product
  await productsStore.loadRecords(product.zzCode, product.productName)
}

function resetTaskForm() {
  if (!currentDepartment.value) {
    return
  }

  taskForm.zzCode = ''
  taskForm.product = ''
  taskForm.worker = ''
  taskForm.department = currentDepartment.value
  taskForm.procedure = ''
  taskForm.quantity = 1
  taskForm.note = ''
}

function selectTaskProduct(value: string) {
  const product = products.value.find((item) => item.zzCode === value)
  taskForm.product = product?.productName ?? ''
}

async function submitTask() {
  await tasksStore.createTask(taskForm)
  resetTaskForm()
}

async function completeTask(taskId: number) {
  if (!currentDepartment.value) {
    return
  }

  await tasksStore.completeTask(taskId, currentDepartment.value)
  await productsStore.loadProducts()
}

function logout() {
  authStore.logout()
  router.replace('/login')
}

async function loadDashboard() {
  await productsStore.loadProducts()

  if (currentDepartment.value) {
    resetTaskForm()
    await tasksStore.loadDepartmentData(currentDepartment.value)
  }
}

onMounted(loadDashboard)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <div class="page-kicker">{{ isAdmin ? 'Admin Dashboard' : 'Task Dashboard' }}</div>
        <h1>{{ isAdmin ? '产品流转看板' : `${currentDepartmentName}任务分配` }}</h1>
        <p v-if="isAdmin">管理员只能新增产品，并查看产品的流转时间线。</p>
        <p v-else>主管在本页面分配任务；任务完成后产品自动流转到下一部门。</p>
      </div>
      <div class="header-actions">
        <ElButton v-if="isAdmin" v-permission="'product:add'" type="primary" @click="openProductDialog">
          新增产品
        </ElButton>
        <ElButton @click="logout">退出</ElButton>
      </div>
    </header>

    <template v-if="isAdmin">
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
            <ElButton text @click="openRecords(product)">流转时间线</ElButton>
          </div>

          <div class="process-line">
            <ElTag v-for="department in product.process" :key="department" effect="plain">
              {{ getDepartmentLabel(department) }}
            </ElTag>
          </div>
        </article>
        <ElEmpty v-if="!productsLoading && products.length === 0" description="暂无产品" />
      </section>

      <aside v-if="activeProduct" class="records-panel">
        <div class="records-head">
          <strong>{{ activeProduct.productName }} 流转时间线</strong>
          <span>{{ records.length }} 条</span>
        </div>
        <ElTimeline>
          <ElTimelineItem v-for="record in records" :key="record.id" :timestamp="record.createdAt">
            {{ getDepartmentLabel(record.fromRepository) }} -> {{ getDepartmentLabel(record.toRepository) }}
            {{ record.quantity }}
            <span v-if="record.note">，{{ record.note }}</span>
          </ElTimelineItem>
        </ElTimeline>
      </aside>
    </template>

    <template v-else>
      <section class="task-layout">
        <div class="assign-panel">
          <h2>分配任务</h2>
          <ElForm :model="taskForm" label-position="top">
            <ElFormItem label="产品">
              <ElSelect v-model="taskForm.zzCode" filterable placeholder="选择产品" @change="selectTaskProduct">
                <ElOption
                  v-for="product in departmentProducts"
                  :key="product.id"
                  :label="`${product.zzCode} / ${product.productName}`"
                  :value="product.zzCode"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="工人">
              <ElSelect v-model="taskForm.worker" filterable allow-create placeholder="选择或输入工人">
                <ElOption v-for="worker in workers" :key="worker.id" :label="worker.name" :value="worker.name" />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="细分工艺">
              <ElSelect v-model="taskForm.procedure" filterable allow-create placeholder="选择或输入工艺">
                <ElOption
                  v-for="procedure in procedures"
                  :key="procedure.id"
                  :label="procedure.procedureName"
                  :value="procedure.procedureName"
                />
              </ElSelect>
            </ElFormItem>
            <ElFormItem label="数量">
              <ElInputNumber v-model="taskForm.quantity" :min="1" />
            </ElFormItem>
            <ElFormItem label="备注">
              <ElInput v-model="taskForm.note" type="textarea" />
            </ElFormItem>
            <ElButton
              v-permission="'task:assign'"
              type="primary"
              :disabled="!taskForm.zzCode || !taskForm.worker || !taskForm.procedure"
              @click="submitTask"
            >
              确认分配
            </ElButton>
          </ElForm>
        </div>

        <div v-loading="tasksLoading" class="task-list">
          <h2>本部门任务</h2>
          <div v-for="task in tasks" :key="task.id" class="task-row">
            <div>
              <strong>{{ task.product }}</strong>
              <span>{{ task.worker }} / {{ task.procedure }} / {{ task.quantity }}</span>
            </div>
            <div class="task-actions">
              <ElTag :type="task.status ? 'success' : 'warning'" effect="light">
                {{ task.status ? '完成' : '进行中' }}
              </ElTag>
              <ElButton
                v-permission="'task:complete'"
                type="primary"
                size="small"
                :disabled="task.status"
                @click="completeTask(task.id)"
              >
                完成
              </ElButton>
            </div>
          </div>
          <ElEmpty v-if="!tasksLoading && tasks.length === 0" description="暂无任务" />
        </div>
      </section>
    </template>

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
.product-card,
.records-panel,
.assign-panel,
.task-list {
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

.product-card,
.records-panel,
.assign-panel,
.task-list {
  padding: 18px;
}

.product-head,
.records-head,
.task-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.process-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.records-panel {
  margin-top: 18px;
}

.task-layout {
  display: grid;
  grid-template-columns: 380px minmax(0, 1fr);
  gap: 18px;
}

.assign-panel h2,
.task-list h2 {
  margin: 0 0 16px;
}

.task-row {
  padding: 14px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: var(--erp-surface-muted);
}

.task-row + .task-row {
  margin-top: 10px;
}

.task-row span {
  display: block;
  margin-top: 4px;
  color: var(--erp-text-muted);
  font-size: 13px;
}

.task-actions,
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
  .header-actions,
  .task-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid,
  .product-grid,
  .task-layout {
    grid-template-columns: 1fr;
  }

  .process-row,
  .process-picker {
    grid-template-columns: 1fr;
  }
}
</style>
