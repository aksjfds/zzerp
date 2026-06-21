<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useProductsStore } from '@/stores/products'
import { useTasksStore } from '@/stores/tasks'
import {
  DEPARTMENT_LABELS,
  type CreateTaskPayload,
  type Department,
  type ProductItem,
} from '@/types/production'

const props = defineProps<{
  department: Department
}>()

const router = useRouter()
const authStore = useAuthStore()
const productsStore = useProductsStore()
const tasksStore = useTasksStore()
const { products } = storeToRefs(productsStore)
const { loading, procedures, tasks, workers } = storeToRefs(tasksStore)
const assignDialogVisible = ref(false)

const taskForm = reactive<CreateTaskPayload>({
  zzCode: '',
  product: '',
  worker: '',
  department: props.department,
  procedure: '',
  quantity: 1,
  note: '',
})

const departmentName = computed(() => DEPARTMENT_LABELS[props.department])
const departmentProducts = computed(() =>
  products.value.filter((product) =>
    product.repositories.some(
      (repository) => repository.department === props.department && repository.quantity > 0,
    ),
  ),
)
const selectedTaskProductStock = computed(() => {
  if (!taskForm.zzCode) {
    return null
  }

  const product = products.value.find((item) => item.zzCode === taskForm.zzCode)
  return product?.repositories.find((repository) => repository.department === props.department) ?? null
})
const selectedAssignableQuantity = computed(() => {
  if (!taskForm.zzCode) {
    return 0
  }

  const product = products.value.find((item) => item.zzCode === taskForm.zzCode)
  return product ? getAssignableQuantity(product) : 0
})

function getDepartmentQuantity(product: ProductItem) {
  return product.repositories
    .filter((repository) => repository.department === props.department)
    .reduce((total, repository) => total + repository.quantity, 0)
}

function getAssignedQuantity(product: ProductItem) {
  return tasks.value
    .filter(
      (task) =>
        !task.status
        && task.zzCode === product.zzCode
        && task.product === product.productName
        && task.department === props.department,
    )
    .reduce((total, task) => total + task.quantity, 0)
}

function getAssignableQuantity(product: ProductItem) {
  return Math.max(getDepartmentQuantity(product) - getAssignedQuantity(product), 0)
}

function resetTaskForm() {
  taskForm.zzCode = ''
  taskForm.product = ''
  taskForm.worker = ''
  taskForm.department = props.department
  taskForm.procedure = ''
  taskForm.quantity = 1
  taskForm.note = ''
}

function selectTaskProduct(value: string) {
  const product = products.value.find((item) => item.zzCode === value)
  taskForm.product = product?.productName ?? ''
  const assignableQuantity = product ? getAssignableQuantity(product) : 0
  taskForm.quantity = assignableQuantity > 0 ? 1 : 0
}

function openAssignDialog(product: ProductItem) {
  resetTaskForm()
  taskForm.zzCode = product.zzCode
  taskForm.product = product.productName
  taskForm.quantity = getAssignableQuantity(product) > 0 ? 1 : 0
  assignDialogVisible.value = true
}

async function addProcedure() {
  const procedureName = taskForm.procedure.trim()

  if (!procedureName) {
    return
  }

  await tasksStore.createProcedure({
    department: props.department,
    procedureName,
  })
  taskForm.procedure = procedureName
}

async function submitTask() {
  await tasksStore.createTask(taskForm)
  assignDialogVisible.value = false
  resetTaskForm()
}

async function completeTask(taskId: number) {
  await tasksStore.completeTask(taskId, props.department)
  await productsStore.loadProducts()
}

function logout() {
  authStore.logout()
  router.replace('/login')
}

async function loadDashboard() {
  await productsStore.loadProducts()
  resetTaskForm()
  await tasksStore.loadDepartmentData(props.department)
}

onMounted(loadDashboard)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <div class="page-kicker">Task Dashboard</div>
        <h1>{{ departmentName }}任务分配</h1>
        <p>主管在本页面分配任务；任务完成后产品自动流转到下一部门。</p>
      </div>
      <div class="header-actions">
        <ElButton @click="logout">退出</ElButton>
      </div>
    </header>

    <section class="task-layout">
      <div class="assign-panel">
        <h2>当前产品</h2>
        <div class="repository-product-list">
          <button
            v-for="product in departmentProducts"
            :key="product.id"
            type="button"
            class="repository-product"
            @click="openAssignDialog(product)"
          >
            <span>{{ product.zzCode }}</span>
            <strong>{{ product.productName }}</strong>
            <em>总计：{{ getDepartmentQuantity(product) }}</em>
            <em>已分配：{{ getAssignedQuantity(product) }}</em>
          </button>
          <ElEmpty v-if="departmentProducts.length === 0" description="暂无本部门产品" :image-size="72" />
        </div>
      </div>

      <div v-loading="loading" class="task-list">
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
        <ElEmpty v-if="!loading && tasks.length === 0" description="暂无任务" />
      </div>
    </section>

    <ElDialog v-model="assignDialogVisible" title="分配任务" width="520px" @closed="resetTaskForm">
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
          <div v-if="selectedTaskProductStock" class="current-stock">
            可分配数量：<strong>{{ selectedAssignableQuantity }}</strong>
          </div>
        </ElFormItem>
        <ElFormItem label="工人">
          <ElSelect v-model="taskForm.worker" filterable allow-create placeholder="选择或输入工人">
            <ElOption v-for="worker in workers" :key="worker.id" :label="worker.name" :value="worker.name" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="工艺">
          <div class="procedure-field">
            <div class="procedure-select-row">
              <ElSelect v-model="taskForm.procedure" filterable allow-create placeholder="选择或输入工艺">
                <ElOption
                  v-for="procedure in procedures"
                  :key="procedure.id"
                  :label="procedure.procedureName"
                  :value="procedure.procedureName"
                />
              </ElSelect>
              <ElButton :disabled="!taskForm.procedure.trim()" @click="addProcedure">添加工艺</ElButton>
            </div>
          </div>
        </ElFormItem>
        <ElFormItem label="数量">
          <ElInputNumber v-model="taskForm.quantity" :min="1" :max="selectedAssignableQuantity || 1" />
        </ElFormItem>
        <ElFormItem label="备注">
          <ElInput v-model="taskForm.note" type="textarea" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="assignDialogVisible = false">取消</ElButton>
        <ElButton
          v-permission="'task:assign'"
          type="primary"
          :disabled="!taskForm.zzCode || !taskForm.worker || !taskForm.procedure || selectedAssignableQuantity <= 0"
          @click="submitTask"
        >
          确认分配
        </ElButton>
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

.page-kicker {
  color: var(--erp-primary);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.dashboard-header h1 {
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

.task-layout {
  display: grid;
  grid-template-columns: 380px minmax(0, 1fr);
  gap: 18px;
}

.assign-panel,
.task-list {
  padding: 18px;
}

.assign-panel h2,
.task-list h2 {
  margin: 0 0 16px;
}

.repository-product-list {
  display: grid;
  gap: 10px;
}

.repository-product {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 14px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: var(--erp-surface-muted);
  color: var(--erp-text);
  cursor: pointer;
  text-align: left;
}

.repository-product:hover {
  border-color: var(--erp-primary);
  background: #eff6ff;
}

.repository-product span,
.repository-product em {
  color: var(--erp-text-muted);
  font-size: 13px;
  font-style: normal;
}

.repository-product strong {
  font-size: 16px;
}

.task-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
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

.task-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-stock {
  margin-top: 8px;
  color: var(--erp-text-muted);
  font-size: 13px;
}

.current-stock strong {
  color: var(--erp-text);
}

.procedure-field {
  width: 100%;
}

.procedure-select-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

@media (max-width: 900px) {
  .dashboard-header,
  .header-actions,
  .task-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .task-layout,
  .procedure-select-row {
    grid-template-columns: 1fr;
  }
}
</style>
