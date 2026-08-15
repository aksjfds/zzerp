<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import AssemblyGroupCards from '../components/AssemblyGroupCards.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import AssemblyWorkOrderDialog from '../components/AssemblyWorkOrderDialog.vue'
import { useAssemblyDepartment } from '../composables/useAssemblyDepartment'
import '../styles/workspace.css'

const controller = useAssemblyDepartment()
const { workspace, assembly, workOrderList, workOrderActions } = controller
const {
  items, loading, pageSize,
  repositoryPage, repositoryTotal, selectedRepository, workers, workshops,
} = workspace
const { items: workOrders, loading: detailLoading, page: historyPage, total: historyTotal } = workOrderList
const {
  activeRepository, applyFilters, changeRepositoryPage, dialogVisible, load, loadDetails, openGroup,
  refresh, saveWorkOrder, selectGroup, selectedGroup, selectedGroupKey, submitting,
} = controller
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
    <DepartmentPageHeader department-name="装配部" description="到达装配节点的配件资料与装配工单。" @refresh="refresh" />
    <DepartmentSectionTabs department-code="assembly">
    <RepositoryFilterBar
      :workshops="workshops"
      mode="assembly"
      @search="applyFilters"
    />
    <section class="production-workspace production-workspace--viewport">
      <div class="production-card production-scroll-column">
        <AssemblyGroupCards :groups="assembly.groups.value" :loading="loading" :selected-key="selectedGroupKey"
          @select="selectGroup" @open="openGroup" />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total"
          :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-execution production-scroll-column">
        <WorkOrderCards v-if="selectedGroup" :items="workOrders" :loading="detailLoading" mode="assembly"
          @submit-qc="workOrderActions.submitQc" @submit-direct-result="workOrderActions.submitDirectResult" @resubmit-qc="workOrderActions.resubmitQc"
          @cancel="workOrderActions.cancel" @undo="workOrderActions.undo" />
        <ElEmpty v-else description="请先选择装配任务" :image-size="64" />
        <ElPagination v-if="selectedGroup" v-model:current-page="historyPage" class="production-pagination" layout="prev, pager, next, total"
          :page-size="pageSize" :total="historyTotal" @current-change="loadDetails" />
      </div>
    </section>
    <AssemblyWorkOrderDialog
      v-model="dialogVisible"
      :item="activeRepository"
      :workers="workOrderWorkers"
      :submitting="submitting"
      @submit="saveWorkOrder" />
    </DepartmentSectionTabs>
  </main>
</template>
