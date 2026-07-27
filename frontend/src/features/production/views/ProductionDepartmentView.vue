<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import ProcedureTagFilterBar from '../components/ProcedureTagFilterBar.vue'
import TagProductionOverview from '../components/TagProductionOverview.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import PurchaseWorkOrderDialog from '../components/PurchaseWorkOrderDialog.vue'
import { useProductionDepartment } from '../composables/useProductionDepartment'
import { workOrderProductionOverview } from '../domain/productionOverview'
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
  openWorkOrder, refresh, saveWorkOrder, selectRepository,
  existingTagIds, applyingTagIds, setExistingTagFilter, setApplyingTagFilter,
  tagItems, tagLoading, submitting,
} = controller
const showSelectedWorkOrders = computed(() => Boolean(selectedRepository.value))
const nonTagOverview = computed(() => workOrderProductionOverview(
  workOrders.value,
  selectedRepository.value?.available_quantity ?? 0,
))
onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      :department-name="departmentName"
      :description="description"
      :workers-path="`/production/${departmentCode}/workers`"
      :tag-config-path="mode === 'production' ? `/production/${departmentCode}/tag-prices` : undefined"
      @refresh="refresh"
    />
    <div class="repository-filter-row">
      <RepositoryFilterBar @search="applyFilters" />
      <ProcedureTagFilterBar
        v-if="mode === 'production'"
        :tags="selectedRepository?.available_tags || []"
        :loading="tagLoading"
        :disabled="!selectedRepository"
        :existing-tag-ids="existingTagIds"
        :applying-tag-ids="applyingTagIds"
        @update:existing-tag-ids="setExistingTagFilter"
        @update:applying-tag-ids="setApplyingTagFilter"
      />
    </div>
    <section class="production-workspace">
      <div class="production-card">
        <RepositoryCards
          :items="items"
          :loading="loading"
          :selected-key="selectedCardKey"
          :mode="mode"
          allow-work-order
          @select="selectRepository"
          @create-work-order="openWorkOrder"
        />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total" :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-execution">
        <TagProductionOverview
          v-if="selectedRepository"
          :items="mode === 'production' ? tagItems : undefined"
          :summary="mode === 'purchase' ? nonTagOverview : undefined"
          :loading="mode === 'production' ? tagLoading : detailLoading"
          :subtitle="mode === 'production' ? '按当前配件和工艺统计' : '按当前外购配件统计'"
          :pending-label="mode === 'production' ? '待打标记' : '待入库'"
          :processing-label="mode === 'production' ? '正在打标记' : '入库处理中'"
          :completed-label="mode === 'production' ? '已打完标记（累计合格）' : '已入库（累计合格）'"
        />
        <WorkOrderCards
          v-if="showSelectedWorkOrders"
          :items="workOrders"
          :loading="detailLoading"
          :mode="mode"
          :department-code="departmentCode"
          @submit="workOrderActions.submit"
          @submit-qc="workOrderActions.submitQc"
          @resubmit-qc="workOrderActions.resubmitQc"
          @cancel="workOrderActions.cancel"
          @undo="workOrderActions.undo"
        />
        <ElEmpty
          v-else
          description="请先选择配件"
          :image-size="64"
        />
        <ElPagination
          v-if="showSelectedWorkOrders"
          v-model:current-page="historyPage"
          class="production-pagination"
          layout="prev, pager, next, total"
          :page-size="pageSize"
          :total="historyTotal"
          @current-change="loadDetails"
        />
      </div>
    </section>
    <CreateWorkOrderDialog
      v-if="mode === 'production'"
      v-model="dialogVisible"
      :item="activeRepository"
      :sources="tagItems"
      :workers="workers"
      :submitting="submitting"
      @submit="saveWorkOrder"
    />
    <PurchaseWorkOrderDialog
      v-else
      v-model="dialogVisible"
      :item="activeRepository"
      :workers="workers"
      :submitting="submitting"
      @submit="saveWorkOrder"
    />
  </main>
</template>

<style scoped>
.repository-filter-row {
  display: flex;
  gap: 12px;
  align-items: stretch;
  margin-bottom: 18px;
}

.repository-filter-row :deep(.repository-filter-bar) {
  min-width: 0;
  flex: 1;
  margin-bottom: 0;
}

@media (max-width: 1280px) {
  .repository-filter-row {
    flex-wrap: wrap;
  }
  .repository-filter-row :deep(.repository-filter-bar),
  .repository-filter-row :deep(.procedure-tag-filters) {
    width: 100%;
    max-width: none;
  }
}

@media (max-width: 760px) {
  .repository-filter-row {
    display: grid;
    grid-template-columns: 1fr;
  }
}
</style>
