<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import { useProductionDepartment } from '../composables/useProductionDepartment'
import '../styles/workspace.css'

const props = withDefaults(defineProps<{
  departmentCode: string
  departmentName: string
  description: string
  specialPrinting?: boolean
}>(), { specialPrinting: false })
const controller = useProductionDepartment(props.departmentCode)
const { workspace, workOrderList, workOrderActions } = controller
const {
  items, loading, pageSize,
  repositoryPage, repositoryTotal, selectedRepository, selectedCardKey, workers, workshops,
} = workspace
const { items: workOrders, loading: detailLoading, page: historyPage, total: historyTotal } = workOrderList
const {
  activeRepository, applyFilters, changeRepositoryPage, dialogVisible, load, loadDetails,
  openWorkOrder, reloadWorkspace, refresh, saveWorkOrder, selectRepository, submitting,
} = controller
const showSelectedWorkOrders = computed(() => Boolean(selectedRepository.value))
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
    <DepartmentPageHeader
      :department-name="departmentName"
      :description="description"
      @refresh="refresh"
    />
    <DepartmentSectionTabs
      :department-code="departmentCode"
      show-inventory
      show-workers
      show-progress
      show-procedure-prices
      @configuration-saved="reloadWorkspace"
    >
    <RepositoryFilterBar
      :workshops="workshops"
      mode="production"
      @search="applyFilters"
    />
    <section class="production-workspace production-workspace--viewport">
      <div class="production-card production-scroll-column">
        <RepositoryCards
          :items="items"
          :loading="loading"
          :selected-key="selectedCardKey"
          allow-work-order
          @select="selectRepository"
          @create-work-order="openWorkOrder"
        />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total" :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-execution production-scroll-column">
        <WorkOrderCards
          v-if="showSelectedWorkOrders"
          :items="workOrders"
          :loading="detailLoading"
          mode="production"
          :special-printing="specialPrinting"
          @submit-qc="workOrderActions.submitQc"
          @submit-direct-result="workOrderActions.submitDirectResult"
          @resubmit-qc="workOrderActions.resubmitQc"
          @cancel="workOrderActions.cancel"
          @undo="workOrderActions.undo"
        />
        <ElEmpty
          v-else
          description="请先选择配件"
          :image-size="64"
        />
        <ElPagination
          v-if="showSelectedWorkOrders"
          v-model:current-page="historyPage"
          class="production-pagination"
          layout="prev, pager, next, total"
          :page-size="pageSize"
          :total="historyTotal"
          @current-change="loadDetails"
        />
      </div>
    </section>
    <CreateWorkOrderDialog
      v-model="dialogVisible"
      :item="activeRepository"
      :workers="workOrderWorkers"
      :submitting="submitting"
      @submit="saveWorkOrder"
    />
    </DepartmentSectionTabs>
  </main>
</template>
