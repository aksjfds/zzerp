<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import QcBatchCards from '../components/QcBatchCards.vue'
import QcInspectionDialog from '../components/QcInspectionDialog.vue'
import TagProductionOverview from '../components/TagProductionOverview.vue'
import { useQcDepartment } from '../composables/useQcDepartment'
import { aggregateProductionOverviewRows } from '../domain/productionOverview'
import type { ProductionOverviewSummary } from '../domain/types'
import '../styles/workspace.css'

const {
  activeView,
  activeBatch,
  batches,
  changePage,
  changeView,
  dialogVisible,
  dispatch,
  load,
  loading,
  openInspection,
  page,
  pageSize,
  refresh,
  saveInspection,
  search,
  submitting,
  total,
  workers,
} = useQcDepartment()
const searchText = ref('')
const productionOverview = computed<ProductionOverviewSummary>(() => {
  const pending = batches.value.filter(item => !item.recorded_at)
  const inspected = batches.value.filter(item => Boolean(item.recorded_at))
  return {
    pendingQuantity: pending.reduce((sum, item) => sum + item.submitted_quantity, 0),
    processingRows: aggregateProductionOverviewRows(pending.map(item => ({
      name: item.work_order_name,
      quantity: item.submitted_quantity,
    }))),
    pendingQcRows: aggregateProductionOverviewRows(inspected.map(item => ({
      name: item.work_order_name,
      quantity: item.dispatchable_quantity,
    }))),
    completedRows: aggregateProductionOverviewRows(inspected.map(item => ({
      name: item.work_order_name,
      quantity: item.qualified_quantity || 0,
    }))),
  }
})

onMounted(load)

function selectView(value: string | number) {
  if (value === 'active' || value === 'history') void changeView(value)
}

function applySearch() {
  void search(searchText.value)
}
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      department-name="QC部门"
      description="录入工单批次质检结果，并将最终合格数量出货到后续流程。"
      workers-path="/production/qc/workers"
      @refresh="refresh"
    />
    <section class="qc-filter-bar">
      <ElInput
        v-model="searchText"
        clearable
        placeholder="搜索工单号、订单号、配件或工单内容"
        @clear="applySearch"
        @keyup.enter="applySearch"
      />
      <ElButton type="primary" @click="applySearch">搜索</ElButton>
    </section>
    <TagProductionOverview
      :loading="loading"
      :summary="productionOverview"
      subtitle="按当前质检列表统计"
      pending-label="待质检"
      processing-label="待录入结果"
      pending-qc-label="合格待出货"
      completed-label="已检合格"
    />
    <section class="production-card qc-workspace">
      <ElTabs :model-value="activeView" @update:model-value="selectView">
        <ElTabPane label="待处理" name="active" />
        <ElTabPane label="历史记录" name="history" />
      </ElTabs>
      <QcBatchCards
        :items="batches"
        :loading="loading"
        :submitting="submitting"
        :history="activeView === 'history'"
        @inspect="openInspection"
        @dispatch="dispatch"
      />
      <ElPagination
        v-model:current-page="page"
        class="production-pagination"
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="total"
        @current-change="changePage"
      />
    </section>
    <QcInspectionDialog
      v-model="dialogVisible"
      :batch="activeBatch"
      :workers="workers"
      :submitting="submitting"
      @submit="saveInspection"
    />
  </main>
</template>

<style scoped>
.qc-workspace { min-height: 300px; }
.qc-filter-bar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) auto;
  gap: 12px;
  margin-bottom: 18px;
}
.qc-heading { display: flex; justify-content: space-between; align-items: center; }
.qc-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
@media (max-width: 640px) {
  .qc-filter-bar { grid-template-columns: 1fr; }
  .qc-filter-bar :deep(.el-button) { width: 100%; }
}
</style>
