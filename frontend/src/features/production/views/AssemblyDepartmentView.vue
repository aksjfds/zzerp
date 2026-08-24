<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import AssemblyGroupCards from '../components/AssemblyGroupCards.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import AssemblyWorkOrderDialog from '../components/AssemblyWorkOrderDialog.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import { useAssemblyDepartment } from '../composables/useAssemblyDepartment'
import '../styles/workspace.css'

const controller = useAssemblyDepartment()
const {
  workspace, assembly, workOrderList, assemblyWorkOrderActions, productionWorkOrderActions,
} = controller
const {
  items, loading, pageSize,
  repositoryPage, repositoryTotal, selectedRepository, workers, workshops,
} = workspace
const { items: workOrders, loading: detailLoading, page: historyPage, total: historyTotal } = workOrderList
const {
  activeRepository, applyFilters, changeRepositoryPage, dialogVisible, load, loadDetails, openGroup,
  openProcess, processDialogVisible, processItems, refresh, saveProcessWorkOrder, saveWorkOrder,
  selectGroup, selectProcess, selectedGroup, selectedGroupKey, selectedMode, submitting,
} = controller
const activeWorkOrderActions = computed(() => selectedMode.value === 'assembly'
  ? assemblyWorkOrderActions
  : productionWorkOrderActions)
const workOrderWorkers = computed(() => {
  const workshop = workshops.value.find(
    item => item.workshop_name === activeRepository.value?.workshop_name,
  )
  if (!workshop) return workers.value
  return workers.value.filter(item => item.workshop_id === workshop.id)
})
onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader department-name="装配部" description="装配任务及装配部所属加工工艺。" @refresh="refresh" />
    <DepartmentSectionTabs
      department-code="assembly"
      show-inventory
      show-workers
      show-progress
      show-procedure-prices
    >
    <RepositoryFilterBar
      :workshops="workshops"
      mode="assembly"
      @search="applyFilters"
    />
    <section class="production-workspace production-workspace--viewport">
      <div class="production-card production-scroll-column">
        <AssemblyGroupCards :groups="assembly.groups.value" :loading="loading" :selected-key="selectedGroupKey" :show-empty="false"
          @select="selectGroup" @open="openGroup" />
        <RepositoryCards :items="processItems" :loading="loading" :selected-key="workspace.selectedCardKey.value"
          :show-empty="false" allow-work-order @select="selectProcess" @create-work-order="openProcess" />
        <ElEmpty v-if="!loading && !assembly.groups.value.length && !processItems.length"
          description="当前暂无装配或加工任务" :image-size="72" />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total"
          :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-execution production-scroll-column">
        <WorkOrderCards v-if="selectedRepository" :items="workOrders" :loading="detailLoading" :mode="selectedMode"
          @submit-qc="activeWorkOrderActions.submitQc" @submit-direct-result="activeWorkOrderActions.submitDirectResult" @resubmit-qc="activeWorkOrderActions.resubmitQc"
          @cancel="activeWorkOrderActions.cancel" @undo="activeWorkOrderActions.undo" />
        <ElEmpty v-else description="请先选择任务" :image-size="64" />
        <ElPagination v-if="selectedRepository" v-model:current-page="historyPage" class="production-pagination" layout="prev, pager, next, total"
          :page-size="pageSize" :total="historyTotal" @current-change="loadDetails" />
      </div>
    </section>
    <AssemblyWorkOrderDialog
      v-model="dialogVisible"
      :item="activeRepository"
      :materials="selectedGroup?.items || []"
      :workers="workOrderWorkers"
      :submitting="submitting"
      @submit="saveWorkOrder" />
    <CreateWorkOrderDialog
      v-model="processDialogVisible"
      :item="activeRepository"
      :workers="workOrderWorkers"
      :submitting="submitting"
      @submit="saveProcessWorkOrder" />
    </DepartmentSectionTabs>
  </main>
</template>
