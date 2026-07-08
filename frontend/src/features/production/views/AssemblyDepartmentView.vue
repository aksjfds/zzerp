<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import AssemblyGroupCards from '../components/AssemblyGroupCards.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import { useDepartmentWorkspace } from '../composables/useDepartmentWorkspace'
import { useAssemblyGroups, type AssemblyGroup } from '../composables/useAssemblyGroups'
import { useWorkOrderActions, useWorkOrderList } from '../composables/useWorkOrders'
import { createAssemblyWorkOrder } from '../api/repositories'
import type { RepositoryItem } from '../domain/types'
import '../styles/workspace.css'

const workspace = useDepartmentWorkspace('assembly', true)
const {
  items, loading, pageSize,
  repositoryPage, repositoryTotal, selectedProductionItemId, selectedRepository, workers,
} = workspace
const assembly = useAssemblyGroups(items)
const workOrderList = useWorkOrderList('assembly', selectedProductionItemId, pageSize)
const { items: workOrders, loading: detailLoading, page: historyPage, total: historyTotal } = workOrderList
const activeRepository = ref<RepositoryItem>()
const dialogVisible = ref(false)
const submitting = ref(false)

const loadDetails = workOrderList.load
async function loadAll() { await workspace.loadRepositories(); await loadDetails() }
function openGroup(group: AssemblyGroup) {
  selectGroup(group)
  assembly.selectGroup(group)
  const maximum = assembly.capacity.value
  if (maximum < 1) return ElMessage.warning('所选物料的可装配数量不足')
  const item = group.items[0]
  activeRepository.value = { ...item, quantity: maximum, available_quantity: maximum }
  dialogVisible.value = true
}
function selectGroup(group: AssemblyGroup) {
  const item = group.items[0]
  workspace.selectRepository(item)
  workOrderList.reset()
  void loadDetails()
}
async function saveWorkOrder(payload: { quantity: number; workerId: number | null }) {
  submitting.value = true
  try {
    await createAssemblyWorkOrder(assembly.selectedIds.value, payload.quantity, payload.workerId)
    dialogVisible.value = false
    assembly.clear()
    await loadAll()
    ElMessage.success('工单已创建')
  } catch (error) { ElMessage.error(getApiErrorDetail(error)?.message || '创建工单失败') }
  finally { submitting.value = false }
}
const workOrderActions = useWorkOrderActions(loadAll)
async function refresh() { workOrderList.reset(); assembly.clear(); await workspace.refresh(); await loadDetails() }
async function applyFilters(filters: Parameters<typeof workspace.search>[0]) {
  workOrderList.reset()
  assembly.clear()
  await workspace.search(filters)
  await loadDetails()
}
onMounted(async () => { await workspace.load(); await loadDetails() })
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader department-name="装配部门" description="到达装配节点的配件资料与装配工单。" @refresh="refresh" />
    <RepositoryFilterBar @search="applyFilters" />
    <section class="production-workspace">
      <div class="production-card">
        <AssemblyGroupCards :groups="assembly.groups.value" :loading="loading" @select="selectGroup" @open="openGroup" />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total"
          :page-size="pageSize" :total="repositoryTotal" />
      </div>
      <div class="production-card production-details">
        <div v-if="selectedRepository" class="production-selection"><strong>{{ selectedRepository.part_no }} - {{
          selectedRepository.part_name }}</strong><span>{{ selectedRepository.customer_order_no }} · {{
              selectedRepository.procedure_name }}</span></div>
        <WorkOrderCards :items="workOrders" :loading="detailLoading" @submit="workOrderActions.submit"
          @cancel="workOrderActions.cancel" />
        <ElPagination v-model:current-page="historyPage" class="production-pagination" layout="prev, pager, next, total"
          :page-size="pageSize" :total="historyTotal" @current-change="loadDetails" />
      </div>
    </section>
    <CreateWorkOrderDialog v-model="dialogVisible" :item="activeRepository" :workers="workers" :submitting="submitting"
      @submit="saveWorkOrder" />
  </main>
</template>
