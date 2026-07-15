<script setup lang="ts">
import { onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
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
  mode?: 'production' | 'purchase'
}>(), { mode: 'production' })
const controller = useProductionDepartment(props.departmentCode, props.mode)
const { workspace, workOrderList, workOrderActions } = controller
const {
  items, loading, pageSize,
  repositoryPage, repositoryTotal, selectedRepository, selectedCardKey, workers,
} = workspace
const { items: workOrders, loading: detailLoading, page: historyPage, total: historyTotal } = workOrderList
const {
  activeRepository, applyFilters, changeRepositoryPage, dialogVisible, load, loadDetails,
  openWorkOrder, refresh, saveWorkOrder, selectRepository, submitting,
} = controller
onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader :department-name="departmentName" :description="description" @refresh="refresh" />
    <RepositoryFilterBar @search="applyFilters" />
    <section class="production-workspace">
      <div class="production-card">
      <RepositoryCards :items="items" :loading="loading" :selected-key="selectedCardKey" :mode="mode" allow-work-order @select="selectRepository" @create-work-order="openWorkOrder" />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total" :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-card production-details">
        <div v-if="selectedRepository" class="production-selection"><strong>{{ selectedRepository.part_no === selectedRepository.part_name ? selectedRepository.part_name : `${selectedRepository.part_no} - ${selectedRepository.part_name}` }}</strong><span>{{ selectedRepository.customer_order_no }} · {{ selectedRepository.procedure_name }}</span></div>
        <WorkOrderCards :items="workOrders" :loading="detailLoading" :mode="mode" @submit="workOrderActions.submit" @cancel="workOrderActions.cancel" />
        <ElPagination v-model:current-page="historyPage" class="production-pagination" layout="prev, pager, next, total" :page-size="pageSize" :total="historyTotal" @current-change="loadDetails" />
      </div>
    </section>
    <CreateWorkOrderDialog v-model="dialogVisible" :item="activeRepository" :workers="workers" :submitting="submitting" :mode="mode" @submit="saveWorkOrder" />
  </main>
</template>
