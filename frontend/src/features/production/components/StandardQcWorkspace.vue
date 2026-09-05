<script setup lang="ts">
import { onMounted, ref } from 'vue'
import QcInspectionBatchTable from './QcInspectionBatchTable.vue'
import QcInspectionDialog from './QcInspectionDialog.vue'
import QcWorkOrderDrawer from './QcWorkOrderDrawer.vue'
import { useQcDepartment } from '../composables/useQcDepartment'
import type { QcInspectionBatchRow, WorkerItem } from '../domain/types'

defineProps<{ workers: WorkerItem[] }>()

const {
  activeView,
  activeBatch,
  changePage,
  changeView,
  decideDestination,
  decidingBatchId,
  dialogVisible,
  load,
  loading,
  batches,
  openInspection,
  page,
  pageSize,
  refresh,
  saveInspection,
  search,
  submitting,
  total,
  undoInspection,
  undoDestination,
  undoingBatchId,
} = useQcDepartment()

const searchText = ref('')
const detailWorkOrderId = ref<number | null>(null)
const detailVisible = ref(false)

function selectView(value: unknown) {
  if (value === 'active' || value === 'history') void changeView(value)
}

function applySearch() {
  void search(searchText.value)
}

function openDetail(batch: QcInspectionBatchRow) {
  detailWorkOrderId.value = batch.work_order_id
  detailVisible.value = true
}

onMounted(load)
defineExpose({ refresh })
</script>

<template>
  <section class="standard-qc-workspace">
    <div class="qc-filter-bar">
      <ElSegmented
        :model-value="activeView"
        :options="[
          { label: '待处理', value: 'active' },
          { label: '历史记录', value: 'history' },
        ]"
        aria-label="质检状态"
        @update:model-value="selectView"
      />
      <ElInput
        v-model="searchText"
        clearable
        placeholder="搜索工单号、订单号、配件或工单内容"
        @clear="applySearch"
        @keyup.enter="applySearch"
      />
      <ElButton type="primary" @click="applySearch">搜索</ElButton>
    </div>

    <section class="qc-workspace">
      <QcInspectionBatchTable
        :items="batches"
        :loading="loading"
        :deciding-batch-id="decidingBatchId"
        :undoing-batch-id="undoingBatchId"
        @inspect="openInspection"
        @view="openDetail"
        @decide="decideDestination"
        @undo-inspection="undoInspection"
        @undo-destination="undoDestination"
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
    <QcWorkOrderDrawer
      v-model="detailVisible"
      :work-order-id="detailWorkOrderId"
    />
  </section>
</template>

<style scoped>
.qc-workspace {
  min-height: 300px;
}

.qc-filter-bar {
  display: grid;
  grid-template-columns: 140px minmax(240px, 1fr) auto;
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
