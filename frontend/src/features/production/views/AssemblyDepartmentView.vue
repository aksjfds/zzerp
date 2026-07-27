<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import AssemblyGroupCards from '../components/AssemblyGroupCards.vue'
import TagProductionOverview from '../components/TagProductionOverview.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import AssemblyWorkOrderDialog from '../components/AssemblyWorkOrderDialog.vue'
import { useAssemblyDepartment } from '../composables/useAssemblyDepartment'
import { workOrderProductionOverview } from '../domain/productionOverview'
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
const productionOverview = computed(() => workOrderProductionOverview(
  workOrders.value,
  selectedGroup.value?.capacity ?? 0,
))
onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader department-name="装配部门" description="到达装配节点的配件资料与装配工单。" workers-path="/production/assembly/workers" @refresh="refresh" />
    <RepositoryFilterBar @search="applyFilters" />
    <section class="production-workspace">
      <div class="production-card">
        <AssemblyGroupCards :groups="assembly.groups.value" :loading="loading" :selected-key="selectedGroupKey"
          @select="selectGroup" @open="openGroup" />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total"
          :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-execution">
        <TagProductionOverview
          v-if="selectedGroup"
          :loading="detailLoading"
          :summary="productionOverview"
          subtitle="按当前装配组合统计"
          pending-label="待装配"
          processing-label="装配中"
          completed-label="已装配（累计合格）"
        />
        <WorkOrderCards :items="workOrders" :loading="detailLoading" mode="assembly" @submit="workOrderActions.submit"
          @submit-qc="workOrderActions.submitQc" @resubmit-qc="workOrderActions.resubmitQc"
          @cancel="workOrderActions.cancel" @undo="workOrderActions.undo" />
        <ElPagination v-model:current-page="historyPage" class="production-pagination" layout="prev, pager, next, total"
          :page-size="pageSize" :total="historyTotal" @current-change="loadDetails" />
      </div>
    </section>
    <AssemblyWorkOrderDialog
      v-model="dialogVisible"
      :item="activeRepository"
      :workers="workers"
      :submitting="submitting"
      @submit="saveWorkOrder" />
  </main>
</template>
