<script setup lang="ts">
import { onMounted } from 'vue'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import AssemblyPositionOverview from '../components/AssemblyPositionOverview.vue'
import AssemblyProductionPositionList from '../components/AssemblyProductionPositionList.vue'
import AssemblyWorkOrderDialog from '../components/AssemblyWorkOrderDialog.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import ProductionProcedureSummary from '../components/ProductionProcedureSummary.vue'
import ProductionWorkbenchFilterBar from '../components/ProductionWorkbenchFilterBar.vue'
import ProductionWorkbenchWorkOrders from '../components/ProductionWorkbenchWorkOrders.vue'
import { useAssemblyWorkbench } from '../composables/useAssemblyWorkbench'
import '../styles/workspace.css'

const workbench = useAssemblyWorkbench()
onMounted(workbench.load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      department-name="装配部"
      description="装配任务及装配部所属加工工艺。"
      @refresh="workbench.refresh"
    />
    <DepartmentSectionTabs
      department-code="assembly"
      show-inventory
      show-workers
      show-progress
      show-procedure-prices
      @configuration-saved="workbench.reloadWorkspace"
    >
      <ProductionWorkbenchFilterBar
        :workshops="workbench.workshops.value"
        @search="workbench.applyFilters"
      />
      <section class="production-workspace production-workspace--viewport workbench-layout">
        <div class="production-card production-scroll-column position-column">
          <AssemblyProductionPositionList
            :items="workbench.positions.value"
            :loading="workbench.positionsLoading.value"
            :selected-key="workbench.selectedPositionKey.value"
            @select="workbench.selectPosition"
          />
          <ElPagination
            v-model:current-page="workbench.positionPage.value"
            class="production-pagination"
            layout="prev, next, total"
            :page-size="workbench.pageSize"
            :total="workbench.positionTotal.value"
            @current-change="workbench.changePositionPage"
          />
        </div>

        <div class="production-execution production-scroll-column workbench-detail-column">
          <template v-if="workbench.selectedPosition.value">
            <AssemblyPositionOverview
              :position="workbench.selectedPosition.value"
              :selected-standard-source="workbench.selectedStandardSource.value"
              :selected-continuation-source="workbench.selectedContinuationSource.value"
              @select-standard-source="workbench.selectStandardSource"
              @select-continuation-source="workbench.selectContinuationSource"
              @create-standard="workbench.openStandardWorkOrder"
              @create-initial-assembly="workbench.openInitialAssemblyWorkOrder"
              @create-continuation="workbench.openContinuationWorkOrder"
            />
            <ProductionProcedureSummary
              :items="workbench.procedureSummaries.value"
              :selected="workbench.isProcedureSelected"
              @select="workbench.selectProcedure"
            />
            <ProductionWorkbenchWorkOrders
              :items="workbench.workOrders.value"
              :loading="workbench.workOrdersLoading.value"
              :special-printing="false"
              :mode="workbench.selectedMode.value"
              @submit-qc="workbench.workOrderActions.value.submitQc"
              @submit-direct-result="workbench.workOrderActions.value.submitDirectResult"
              @resubmit-qc="workbench.workOrderActions.value.resubmitQc"
              @cancel="workbench.workOrderActions.value.cancel"
              @undo="workbench.workOrderActions.value.undo"
            />
            <ElPagination
              v-model:current-page="workbench.workOrderPage.value"
              class="production-pagination"
              layout="prev, pager, next, total"
              :page-size="workbench.pageSize"
              :total="workbench.workOrderTotal.value"
              @current-change="workbench.changeWorkOrderPage"
            />
          </template>
          <ElEmpty v-else description="请选择在位物料查看加工情况" :image-size="72" />
        </div>
      </section>

      <CreateWorkOrderDialog
        v-model="workbench.standardDialogVisible.value"
        :item="workbench.standardCreationTarget.value"
        :workers="workbench.workOrderWorkers.value"
        :submitting="workbench.submitting.value"
        @submit="workbench.saveStandardWorkOrder"
      />
      <AssemblyWorkOrderDialog
        v-model="workbench.assemblyDialogVisible.value"
        :item="workbench.activeAssemblyTarget.value"
        :workers="workbench.workOrderWorkers.value"
        :submitting="workbench.submitting.value"
        @submit="workbench.saveAssemblyWorkOrder"
      />
    </DepartmentSectionTabs>
  </main>
</template>

<style scoped>
.workbench-layout { grid-template-columns: minmax(320px, 390px) minmax(0, 1fr); }
.position-column { padding: 14px; }
.workbench-detail-column { gap: 12px; padding-right: 3px; overflow-y: auto !important; scrollbar-gutter: stable; }
.workbench-detail-column > :first-child { min-height: auto !important; flex: 0 0 auto !important; overflow: visible !important; }
.workbench-detail-column > :deep(.el-empty) { margin: auto; }
@media (max-width: 900px) {
  .workbench-layout { grid-template-columns: 1fr; }
  .workbench-detail-column { overflow-y: visible !important; }
}
</style>
