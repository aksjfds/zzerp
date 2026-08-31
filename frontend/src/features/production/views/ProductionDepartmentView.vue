<script setup lang="ts">
import { onMounted } from 'vue'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import ProductionPositionList from '../components/ProductionPositionList.vue'
import ProductionPositionOverview from '../components/ProductionPositionOverview.vue'
import ProductionProcedureSummary from '../components/ProductionProcedureSummary.vue'
import ProductionWorkbenchFilterBar from '../components/ProductionWorkbenchFilterBar.vue'
import ProductionWorkbenchWorkOrders from '../components/ProductionWorkbenchWorkOrders.vue'
import { useProductionWorkbench } from '../composables/useProductionWorkbench'
import '../styles/workspace.css'

const props = withDefaults(defineProps<{
  departmentCode: string
  departmentName: string
  description: string
  specialPrinting?: boolean
}>(), { specialPrinting: false })
const workbench = useProductionWorkbench(props.departmentCode)

onMounted(workbench.load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      :department-name="departmentName"
      :description="description"
      @refresh="workbench.refresh"
    />
    <DepartmentSectionTabs
      :department-code="departmentCode"
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
          <ProductionPositionList
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
            <ProductionPositionOverview
              :position="workbench.selectedPosition.value"
              :selected-source="workbench.selectedSource.value"
              @select-source="workbench.selectSource"
              @create-work-order="workbench.openWorkOrder"
            />
            <ProductionProcedureSummary
              :items="workbench.procedureSummaries.value"
              :selected="workbench.isProcedureSelected"
              @select="workbench.selectProcedure"
            />
            <ProductionWorkbenchWorkOrders
              :items="workbench.workOrders.value"
              :loading="workbench.workOrdersLoading.value"
              :special-printing="specialPrinting"
              @submit-qc="workbench.workOrderActions.submitQc"
              @submit-direct-result="workbench.workOrderActions.submitDirectResult"
              @resubmit-qc="workbench.workOrderActions.resubmitQc"
              @cancel="workbench.workOrderActions.cancel"
              @undo="workbench.workOrderActions.undo"
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
        v-model="workbench.dialogVisible.value"
        :item="workbench.creationTarget.value"
        :workers="workbench.workOrderWorkers.value"
        :submitting="workbench.submitting.value"
        @submit="workbench.saveWorkOrder"
      />
    </DepartmentSectionTabs>
  </main>
</template>

<style scoped>
.workbench-layout { grid-template-columns: minmax(310px, 370px) minmax(0, 1fr); }
.position-column { padding: 14px; }
.workbench-detail-column { gap: 12px; padding-right: 3px; overflow-y: auto !important; scrollbar-gutter: stable; }
.workbench-detail-column > :first-child { min-height: auto !important; flex: 0 0 auto !important; overflow: visible !important; }
.workbench-detail-column > :deep(.el-empty) { margin: auto; }
@media (max-width: 900px) {
  .workbench-layout { grid-template-columns: 1fr; }
  .workbench-detail-column { overflow-y: visible !important; }
}
</style>
