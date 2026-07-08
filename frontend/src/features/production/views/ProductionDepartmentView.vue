<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import { useDepartmentWorkspace } from '../composables/useDepartmentWorkspace'
import { useWorkOrderActions, useWorkOrderList } from '../composables/useWorkOrders'
import { createWorkOrder } from '../api/repositories'
import type { RepositoryItem } from '../domain/types'
import '../styles/workspace.css'

const props = defineProps<{ departmentCode: string; departmentName: string; description: string }>()
const workspace = useDepartmentWorkspace(props.departmentCode, true)
const {
  items, loading, pageSize,
  repositoryPage, repositoryTotal, selectedProductionItemId, selectedRepository, selectedCardKey, workers,
} = workspace
const workOrderList = useWorkOrderList(props.departmentCode, selectedProductionItemId, pageSize)
const { items: workOrders, loading: detailLoading, page: historyPage, total: historyTotal } = workOrderList
const activeRepository = ref<RepositoryItem>()
const dialogVisible = ref(false)
const submitting = ref(false)

const loadDetails = workOrderList.load
async function loadAll() {
  await workspace.loadRepositories()
  await loadDetails()
}
function selectRepository(item: RepositoryItem) {
  workspace.selectRepository(item)
  workOrderList.reset()
  void loadDetails()
}
function openWorkOrder(item: RepositoryItem) {
  selectRepository(item)
  activeRepository.value = item
  dialogVisible.value = true
}
async function saveWorkOrder(payload: { quantity: number; workerId: number | null }) {
  if (!activeRepository.value?.repository_id) return
  submitting.value = true
  try {
    await createWorkOrder(activeRepository.value.repository_id, payload.quantity, payload.workerId)
    dialogVisible.value = false
    await loadAll()
    ElMessage.success('工单已创建')
  } catch (error) { ElMessage.error(getApiErrorDetail(error)?.message || '创建工单失败') }
  finally { submitting.value = false }
}
const workOrderActions = useWorkOrderActions(loadAll)
async function refresh() {
  workOrderList.reset()
  await workspace.refresh()
  await loadDetails()
}
async function applyFilters(filters: Parameters<typeof workspace.search>[0]) {
  workOrderList.reset()
  await workspace.search(filters)
  await loadDetails()
}
onMounted(async () => { await workspace.load(); await loadDetails() })
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader :department-name="departmentName" :description="description" @refresh="refresh" />
    <RepositoryFilterBar @search="applyFilters" />
    <section class="production-workspace">
      <div class="production-card">
      <RepositoryCards :items="items" :loading="loading" :selected-key="selectedCardKey" allow-work-order @select="selectRepository" @create-work-order="openWorkOrder" />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total" :page-size="pageSize" :total="repositoryTotal" />
      </div>
      <div class="production-card production-details">
        <div v-if="selectedRepository" class="production-selection"><strong>{{ selectedRepository.part_no }} - {{ selectedRepository.part_name }}</strong><span>{{ selectedRepository.customer_order_no }} · {{ selectedRepository.procedure_name }}</span></div>
        <WorkOrderCards :items="workOrders" :loading="detailLoading" @submit="workOrderActions.submit" @cancel="workOrderActions.cancel" />
        <ElPagination v-model:current-page="historyPage" class="production-pagination" layout="prev, pager, next, total" :page-size="pageSize" :total="historyTotal" @current-change="loadDetails" />
      </div>
    </section>
    <CreateWorkOrderDialog v-model="dialogVisible" :item="activeRepository" :workers="workers" :submitting="submitting" @submit="saveWorkOrder" />
  </main>
</template>
