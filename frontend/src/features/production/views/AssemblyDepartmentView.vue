<script setup lang="ts">
import { onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import AssemblyGroupCards from '../components/AssemblyGroupCards.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import { useAssemblyDepartment } from '../composables/useAssemblyDepartment'
import '../styles/workspace.css'

const controller = useAssemblyDepartment()
const { workspace, assembly, workOrderList, workOrderActions } = controller
const {
  items, loading, pageSize,
  repositoryPage, repositoryTotal, selectedRepository, workers,
} = workspace
const { items: workOrders, loading: detailLoading, page: historyPage, total: historyTotal } = workOrderList
const {
  activeRepository, applyFilters, changeRepositoryPage, dialogVisible, load, loadDetails, openGroup,
  refresh, saveWorkOrder, selectGroup, selectedGroup, selectedGroupKey, submitting,
} = controller
onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader department-name="装配部门" description="到达装配节点的配件资料与装配工单。" @refresh="refresh" />
    <RepositoryFilterBar @search="applyFilters" />
    <section class="production-workspace">
      <div class="production-card">
        <AssemblyGroupCards :groups="assembly.groups.value" :loading="loading" :selected-key="selectedGroupKey"
          @select="selectGroup" @open="openGroup" />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total"
          :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-card production-details">
        <div v-if="selectedRepository" class="production-selection"><strong>{{ selectedRepository.part_no }} - {{
          selectedGroup?.name || selectedRepository.part_name }}</strong><span>{{ selectedRepository.customer_order_no }} · {{
              selectedRepository.procedure_name }}</span></div>
        <WorkOrderCards :items="workOrders" :loading="detailLoading" mode="assembly" @submit="workOrderActions.submit"
          @cancel="workOrderActions.cancel" />
        <ElPagination v-model:current-page="historyPage" class="production-pagination" layout="prev, pager, next, total"
          :page-size="pageSize" :total="historyTotal" @current-change="loadDetails" />
      </div>
    </section>
    <CreateWorkOrderDialog v-model="dialogVisible" :item="activeRepository" :workers="workers" :submitting="submitting" mode="assembly"
      @submit="saveWorkOrder" />
  </main>
</template>
