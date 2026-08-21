<script setup lang="ts">
import { onMounted, ref } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import QcBatchCards from '../components/QcBatchCards.vue'
import QcInspectionDialog from '../components/QcInspectionDialog.vue'
import { useQcDepartment } from '../composables/useQcDepartment'
import '../styles/workspace.css'

const {
  activeView,
  activeBatch,
  batches,
  changePage,
  changeView,
  dialogVisible,
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
      description="录入工单质检结果，并决定合格品返回当前车间或放行下一节点。"
      @refresh="refresh"
    />
    <DepartmentSectionTabs department-code="qc">
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
    <section class="production-card qc-workspace">
      <ElTabs :model-value="activeView" @update:model-value="selectView">
        <ElTabPane label="待处理" name="active" />
        <ElTabPane label="历史记录" name="history" />
      </ElTabs>
      <QcBatchCards
        :items="batches"
        :loading="loading"
        :history="activeView === 'history'"
        @inspect="openInspection"
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
    </DepartmentSectionTabs>
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
