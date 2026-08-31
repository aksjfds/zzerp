<script setup lang="ts">
import { onMounted, ref } from 'vue'
import QcBatchCards from './QcBatchCards.vue'
import QcInspectionDialog from './QcInspectionDialog.vue'
import { useQcDepartment } from '../composables/useQcDepartment'
import type { WorkerItem } from '../domain/types'

defineProps<{ workers: WorkerItem[] }>()

const {
  activeView,
  activeBatch,
  batches,
  changePage,
  changeView,
  decideDestination,
  decidingBatchId,
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
} = useQcDepartment()

const searchText = ref('')

function selectView(value: string | number) {
  if (value === 'active' || value === 'history') void changeView(value)
}

function applySearch() {
  void search(searchText.value)
}

onMounted(load)
defineExpose({ refresh })
</script>

<template>
  <section class="standard-qc-workspace">
    <div class="qc-filter-bar">
      <ElInput
        v-model="searchText"
        clearable
        placeholder="搜索工单号、订单号、配件或工单内容"
        @clear="applySearch"
        @keyup.enter="applySearch"
      />
      <ElButton type="primary" @click="applySearch">搜索</ElButton>
    </div>

    <section class="production-card qc-workspace">
      <ElTabs :model-value="activeView" @update:model-value="selectView">
        <ElTabPane label="待处理" name="active" />
        <ElTabPane label="历史记录" name="history" />
      </ElTabs>
      <QcBatchCards
        :items="batches"
        :loading="loading"
        :history="activeView === 'history'"
        :deciding-batch-id="decidingBatchId"
        @inspect="openInspection"
        @decide="decideDestination"
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
  </section>
</template>

<style scoped>
.qc-workspace {
  min-height: 300px;
}

.qc-filter-bar {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) auto;
  gap: 12px;
  margin-bottom: 18px;
}

@media (max-width: 640px) {
  .qc-filter-bar {
    grid-template-columns: 1fr;
  }

  .qc-filter-bar :deep(.el-button) {
    width: 100%;
  }
}
</style>
