<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorDetail } from '@/api/request'
import RepositoryCards from '../components/RepositoryCards.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import {
  createWorkOrder,
  createAssemblyWorkOrder,
  cancelWorkOrder,
  inspectQcBatch,
  queryDepartmentProductionObjects,
  queryDepartmentRepositories,
  queryDepartmentWorkOrders,
  queryDepartmentWorkers,
  queryPendingQcBatches,
  submitWorkOrder,
} from '../api/repositories'
import type {
  PendingQcBatch,
  QcInspectionPayload,
  RepositoryItem,
  WorkOrder,
  WorkerItem,
} from '../domain/types'

const props = defineProps<{
  departmentCode: string
  departmentName: string
  description: string
}>()
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const detailLoading = ref(false)
const keyword = ref('')
const items = ref<RepositoryItem[]>([])
const workOrders = ref<WorkOrder[]>([])
const workers = ref<WorkerItem[]>([])
const pendingQc = ref<PendingQcBatch[]>([])
const repositoryPage = ref(1)
const historyPage = ref(1)
const historyIndexPage = ref(1)
const pageSize = 50
const repositoryTotal = ref(0)
const historyTotal = ref(0)
const historyIndexTotal = ref(0)
const knownHistoryOptions = ref(new Map<number, { id: number; label: string }>())
const selectedRepositoryId = ref<number | null>(null)
const selectedProductionItemId = ref<number | null>(null)
const activeRepository = ref<RepositoryItem>()
const workOrderVisible = ref(false)
const workOrderSubmitting = ref(false)
const assemblySelections = ref(new Map<number, RepositoryItem>())
const activeAssemblyRepositoryIds = computed(() => [...assemblySelections.value.keys()])
const activeBatch = ref<PendingQcBatch>()
const inspectionVisible = ref(false)
const inspection = reactive<QcInspectionPayload>({
  qualified_quantity: 0,
  rework_quantity: 0,
  scrap_quantity: 0,
  lost_quantity: 0,
  defect_reason: '',
})
let loadSequence = 0
let detailLoadSequence = 0
const supportsWorkOrders = computed(() => ['stamp', 'polish', 'assembly'].includes(props.departmentCode))
const isAssembly = computed(() => props.departmentCode === 'assembly')
const isQc = computed(() => props.departmentCode === 'qc')
const filteredItems = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  if (!value) return items.value
  return items.value.filter((item) => [
    item.customer_order_no,
    item.customer_name,
    item.factory_code,
    item.product_name,
    item.part_name,
    item.part_no,
    item.procedure_name,
  ].some((field) => field.toLowerCase().includes(value)))
})
const selectedRepository = computed(() => items.value.find(
  item => item.id === selectedRepositoryId.value,
))
const visibleWorkOrders = computed(() => workOrders.value)
const visibleQcBatches = computed(() => pendingQc.value)
const historyOptions = computed(() => {
  const unique = new Map(knownHistoryOptions.value)
  items.value.forEach((item) => unique.set(item.production_item_id, {
    id: item.production_item_id,
    label: `${item.customer_order_no} · ${item.part_no} - ${item.part_name}`,
  }))
  return [...unique.values()]
})
const selectedAssemblyItems = computed(() => [...assemblySelections.value.values()])
const assemblyCapacity = computed(() => {
  if (selectedAssemblyItems.value.length < 2) return 0
  return Math.min(...selectedAssemblyItems.value.map(item => (
    Math.floor(item.available_quantity / item.assembly_unit_quantity)
  )))
})
async function loadItems() {
  const sequence = ++loadSequence
  loading.value = true
  items.value = []
  workers.value = []
  repositoryTotal.value = 0
  historyIndexTotal.value = 0
  try {
    const [repositoryResult, historyResult, workersResult] = await Promise.allSettled([
      queryDepartmentRepositories(props.departmentCode, repositoryPage.value, pageSize),
      (supportsWorkOrders.value || isQc.value)
        ? queryDepartmentProductionObjects(
          props.departmentCode,
          historyIndexPage.value,
          pageSize,
        )
        : Promise.resolve({ items: [], total: 0 }),
      supportsWorkOrders.value ? queryDepartmentWorkers(props.departmentCode) : Promise.resolve([]),
    ])
    if (sequence !== loadSequence) return
    if (repositoryResult.status === 'rejected') throw repositoryResult.reason
    const repositoryItems = repositoryResult.value.items
    let pageAdjusted = false
    const lastRepositoryPage = Math.max(1, Math.ceil(repositoryResult.value.total / pageSize))
    if (!repositoryItems.length && repositoryPage.value > lastRepositoryPage) {
      repositoryPage.value = lastRepositoryPage
      pageAdjusted = true
    }
    if (
      historyResult.status === 'fulfilled'
      && !historyResult.value.items.length
      && historyIndexPage.value > Math.max(1, Math.ceil(historyResult.value.total / pageSize))
    ) {
      historyIndexPage.value = Math.max(1, Math.ceil(historyResult.value.total / pageSize))
      pageAdjusted = true
    }
    if (pageAdjusted) {
      await loadItems()
      return
    }
    items.value = repositoryItems
    repositoryTotal.value = repositoryResult.value.total
    if (historyResult.status === 'fulfilled') {
      historyResult.value.items.forEach(item => knownHistoryOptions.value.set(
        item.production_item_id,
        {
          id: item.production_item_id,
          label: `${item.customer_order_no} · ${item.part_no} - ${item.part_name}`,
        },
      ))
      historyIndexTotal.value = historyResult.value.total
    }
    else ElMessage.warning('历史生产对象加载失败')
    if (workersResult.status === 'fulfilled') workers.value = workersResult.value
    else ElMessage.warning('工人列表加载失败')
    if (!repositoryItems.some(item => item.id === selectedRepositoryId.value)) {
      selectedRepositoryId.value = null
    }
    if (!selectedProductionItemId.value) {
      selectedProductionItemId.value = repositoryItems[0]?.production_item_id
        ?? historyOptions.value[0]?.id
        ?? null
    }
    await loadDetails()
  }
  catch { ElMessage.error('部门生产资料加载失败') }
  finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function loadDetails() {
  const sequence = ++detailLoadSequence
  detailLoading.value = true
  workOrders.value = []
  pendingQc.value = []
  historyTotal.value = 0
  if (!selectedProductionItemId.value) {
    detailLoading.value = false
    return
  }
  try {
    if (supportsWorkOrders.value) {
      const result = await queryDepartmentWorkOrders(
        props.departmentCode,
        historyPage.value,
        pageSize,
        selectedProductionItemId.value,
      )
      if (sequence !== detailLoadSequence) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (!result.items.length && historyPage.value > lastPage) {
        historyPage.value = lastPage
        await loadDetails()
        return
      }
      workOrders.value = result.items
      historyTotal.value = result.total
    } else if (isQc.value) {
      const result = await queryPendingQcBatches(
        historyPage.value,
        pageSize,
        selectedProductionItemId.value,
      )
      if (sequence !== detailLoadSequence) return
      const lastPage = Math.max(1, Math.ceil(result.total / pageSize))
      if (!result.items.length && historyPage.value > lastPage) {
        historyPage.value = lastPage
        await loadDetails()
        return
      }
      pendingQc.value = result.items
      historyTotal.value = result.total
    }
  } catch {
    if (sequence === detailLoadSequence) ElMessage.warning('关联生产记录加载失败')
  } finally {
    if (sequence === detailLoadSequence) detailLoading.value = false
  }
}

function refreshItems() {
  detailLoadSequence += 1
  detailLoading.value = false
  workOrders.value = []
  pendingQc.value = []
  historyTotal.value = 0
  knownHistoryOptions.value.clear()
  selectedRepositoryId.value = null
  selectedProductionItemId.value = null
  historyIndexPage.value = 1
  historyPage.value = 1
  void loadItems()
}

function selectRepository(item: RepositoryItem) {
  selectedRepositoryId.value = item.id
  selectedProductionItemId.value = item.production_item_id
  historyPage.value = 1
  void loadDetails()
}

function toggleAssemblyInput(item: RepositoryItem) {
  if (assemblySelections.value.has(item.id)) assemblySelections.value.delete(item.id)
  else {
    const first = selectedAssemblyItems.value[0]
    if (first && (
      first.customer_order_item_id !== item.customer_order_item_id
      || first.flow_node_id !== item.flow_node_id
    )) {
      ElMessage.warning('装配输入必须属于同一订单产品和装配节点')
      return
    }
    assemblySelections.value.set(item.id, item)
  }
}

function selectProductionItem(productionItemId: number) {
  selectedProductionItemId.value = productionItemId
  historyPage.value = 1
  void loadDetails()
}

function changeHistoryIndexPage() {
  void loadItems()
}

function openWorkOrder(item: RepositoryItem) {
  selectedRepositoryId.value = item.id
  selectedProductionItemId.value = item.production_item_id
  if (isAssembly.value) {
    const inputs = selectedAssemblyItems.value
    if (inputs.length < 2) {
      ElMessage.warning('请至少选择两个装配输入')
      return
    }
    const maximum = assemblyCapacity.value
    if (maximum < 1) {
      ElMessage.warning('所选物料的可装配数量不足')
      return
    }
    activeRepository.value = { ...item, quantity: maximum, available_quantity: maximum }
  } else {
    assemblySelections.value.clear()
    activeRepository.value = item
  }
  workOrderVisible.value = true
}

async function saveWorkOrder(payload: { quantity: number; workerId: number | null }) {
  if (!activeRepository.value) return
  workOrderSubmitting.value = true
  try {
    if (isAssembly.value) {
      await createAssemblyWorkOrder(
        activeAssemblyRepositoryIds.value,
        payload.quantity,
        payload.workerId,
      )
    } else {
      await createWorkOrder(activeRepository.value.id, payload.quantity, payload.workerId)
    }
    workOrderVisible.value = false
    assemblySelections.value.clear()
    await loadItems()
    ElMessage.success('工单已创建')
  } catch (error) { ElMessage.error(getApiErrorDetail(error)?.message || '创建工单失败') }
  finally { workOrderSubmitting.value = false }
}

async function submitOrder(item: WorkOrder) {
  const remaining = item.quantity - item.submitted_quantity
  try {
    const { value } = await ElMessageBox.prompt('请输入本次完成或送检数量', '工艺完成', {
      inputValue: String(remaining),
      inputPattern: /^[1-9]\d*$/,
      inputErrorMessage: '请输入正整数',
    })
    await submitWorkOrder(item.id, Number(value))
    await loadItems()
    ElMessage.success('工艺结果已提交')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '工艺提交失败')
    }
  }
}

async function cancelOrder(item: WorkOrder) {
  try {
    await ElMessageBox.confirm(`确认取消工单 ${item.work_order_no}？`, '取消工单')
    await cancelWorkOrder(item.id)
    await loadItems()
    ElMessage.success('工单已取消')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '取消工单失败')
    }
  }
}

function openInspection(batch: PendingQcBatch) {
  activeBatch.value = batch
  Object.assign(inspection, {
    qualified_quantity: batch.submitted_quantity,
    rework_quantity: 0,
    scrap_quantity: 0,
    lost_quantity: 0,
    defect_reason: '',
  })
  inspectionVisible.value = true
}

async function saveInspection() {
  if (!activeBatch.value) return
  const total = inspection.qualified_quantity + inspection.rework_quantity
    + inspection.scrap_quantity + inspection.lost_quantity
  if (total !== activeBatch.value.submitted_quantity) {
    return ElMessage.warning('质检结果合计必须等于送检数量')
  }
  try {
    await inspectQcBatch(activeBatch.value.id, inspection)
    inspectionVisible.value = false
    await loadItems()
    ElMessage.success('QC 结果已录入')
  } catch (error) { ElMessage.error(getApiErrorDetail(error)?.message || 'QC 结果录入失败') }
}

async function logout() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(loadItems)
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div><span>{{ departmentName }}</span><h1>{{ departmentName }}工作台</h1><p>{{ description }}</p></div>
      <div><ElButton @click="refreshItems">刷新</ElButton><ElButton @click="logout">退出登录</ElButton></div>
    </header>
    <section class="workspace-grid">
      <div class="content-card">
        <div class="toolbar"><ElInput v-model="keyword" clearable placeholder="搜索当前页的订单、产品或配件" /></div>
        <RepositoryCards
          :items="filteredItems"
          :loading="loading"
          :selected-id="selectedRepositoryId"
          :allow-work-order="supportsWorkOrders && !isAssembly"
          :multi-selectable="isAssembly"
          :selected-ids="activeAssemblyRepositoryIds"
          @select="selectRepository"
          @toggle="toggleAssemblyInput"
          @create-work-order="openWorkOrder"
        />
        <ElPagination
          v-model:current-page="repositoryPage"
          class="pagination"
          layout="prev, next, total"
          :page-size="pageSize"
          :total="repositoryTotal"
          @current-change="loadItems"
        />
        <ElButton
          v-if="isAssembly"
          type="primary"
          class="assembly-create"
          :disabled="activeAssemblyRepositoryIds.length < 2 || assemblyCapacity < 1"
          @click="openWorkOrder(selectedAssemblyItems[0]!)"
        >为所选物料开装配工单</ElButton>
      </div>
      <div class="content-card work-orders">
        <div class="history-selector">
          <span>当前 / 历史生产对象</span>
          <ElSelect v-model="selectedProductionItemId" placeholder="选择配件或装配体" @change="selectProductionItem">
            <ElOption v-for="option in historyOptions" :key="option.id" :label="option.label" :value="option.id" />
          </ElSelect>
          <ElPagination
            v-if="historyIndexTotal > pageSize"
            v-model:current-page="historyIndexPage"
            class="history-index-pagination"
            layout="prev, next"
            :page-size="pageSize"
            :total="historyIndexTotal"
            @current-change="changeHistoryIndexPage"
          />
        </div>
        <div v-if="selectedRepository" class="selection-title">
          <strong>{{ selectedRepository.part_no }} - {{ selectedRepository.part_name }}</strong>
          <span>{{ selectedRepository.customer_order_no }} · {{ selectedRepository.procedure_name }}</span>
        </div>
        <!-- <h2>工单</h2> -->
        <template v-if="isQc">
          <div v-loading="detailLoading" class="qc-list">
            <article v-for="batch in visibleQcBatches" :key="batch.id" class="qc-card">
              <strong>{{ batch.work_order_no }}</strong>
              <p>{{ batch.part_no }} - {{ batch.part_name }}</p>
              <p>工艺：{{ batch.procedure_name }} · 送检：{{ batch.submitted_quantity }}</p>
              <template v-if="batch.recorded_at">
                <p>合格 {{ batch.qualified_quantity || 0 }} · 返工 {{ batch.rework_quantity || 0 }} · 报废 {{ batch.scrap_quantity || 0 }} · 遗失 {{ batch.lost_quantity || 0 }}</p>
                <p>QC：{{ batch.qc_worker_name }} · {{ batch.recorded_at }}</p>
                <p v-if="batch.defect_reason">不良原因：{{ batch.defect_reason }}</p>
              </template>
              <ElButton v-else type="primary" size="small" @click="openInspection(batch)">录入 QC 结果</ElButton>
            </article>
            <ElEmpty v-if="!visibleQcBatches.length" description="所选配件暂无 QC 记录" :image-size="64" />
          </div>
        </template>
        <WorkOrderCards
          v-else-if="supportsWorkOrders"
          :items="visibleWorkOrders"
          :loading="detailLoading"
          @submit="submitOrder"
          @cancel="cancelOrder"
        />
        <ElEmpty v-else description="暂无可操作内容" :image-size="64" />
        <ElPagination
          v-if="supportsWorkOrders || isQc"
          v-model:current-page="historyPage"
          class="pagination"
          layout="prev, pager, next, total"
          :page-size="pageSize"
          :total="historyTotal"
          @current-change="loadDetails"
        />
      </div>
    </section>
    <CreateWorkOrderDialog
      v-model="workOrderVisible"
      :item="activeRepository"
      :workers="workers"
      :submitting="workOrderSubmitting"
      @submit="saveWorkOrder"
    />
    <ElDialog v-model="inspectionVisible" title="录入 QC 结果" width="520px">
      <p class="inspection-title">送检数量：{{ activeBatch?.submitted_quantity }}</p>
      <div class="inspection-grid">
        <ElFormItem label="合格"><ElInputNumber v-model="inspection.qualified_quantity" :min="0" /></ElFormItem>
        <ElFormItem label="返工"><ElInputNumber v-model="inspection.rework_quantity" :min="0" /></ElFormItem>
        <ElFormItem label="报废"><ElInputNumber v-model="inspection.scrap_quantity" :min="0" /></ElFormItem>
        <ElFormItem label="遗失"><ElInputNumber v-model="inspection.lost_quantity" :min="0" /></ElFormItem>
      </div>
      <ElFormItem label="不良原因"><ElInput v-model="inspection.defect_reason" type="textarea" /></ElFormItem>
      <template #footer><ElButton @click="inspectionVisible = false">取消</ElButton><ElButton type="primary" @click="saveInspection">确认录入</ElButton></template>
    </ElDialog>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: 24px; background: var(--erp-bg); }
.page-header, .content-card { border: 1px solid var(--erp-border); border-radius: 10px; background: #fff; box-shadow: var(--erp-shadow-sm); }
.page-header { display: flex; justify-content: space-between; gap: 20px; align-items: center; margin-bottom: 18px; padding: 20px 24px; }
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 5px 0; font-size: 24px; }
.page-header p { margin: 0; color: var(--el-text-color-secondary); }
.content-card { margin-bottom: 18px; padding: 20px; }
.content-card h2 { margin: 0; font-size: 17px; }
.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.toolbar .el-input { width: 360px; }
.assembly-create { width: 100%; margin-top: 14px; }
.workspace-grid { display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr); gap: 18px; align-items: start; }
.work-orders { min-height: 260px; }
.history-selector { display: flex; gap: 12px; align-items: center; margin-bottom: 14px; }
.history-selector span { flex: 0 0 auto; color: var(--el-text-color-secondary); font-size: 13px; }
.history-selector .el-select { width: min(100%, 440px); }
.history-index-pagination { flex: 0 0 auto; }
.selection-title { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding-bottom: 14px; border-bottom: 1px solid var(--erp-border); }
.selection-title span { color: var(--el-text-color-secondary); font-size: 13px; }
.qc-list { display: grid; gap: 12px; margin-top: 14px; }
.qc-card { padding: 14px; border: 1px solid var(--erp-border); border-radius: 8px; background: #f8fafc; }
.qc-card p { margin: 7px 0; color: var(--el-text-color-secondary); font-size: 13px; }
.inspection-title { margin-top: 0; font-weight: 700; }
.inspection-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.pagination { justify-content: flex-end; margin-top: 14px; }
@media (max-width: 900px) { .workspace-grid { grid-template-columns: 1fr; } .page-header { align-items: flex-start; flex-direction: column; } }
</style>
