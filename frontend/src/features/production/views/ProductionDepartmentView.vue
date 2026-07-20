<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import ProcedureTagFilterBar from '../components/ProcedureTagFilterBar.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import PurchaseWorkOrderDialog from '../components/PurchaseWorkOrderDialog.vue'
import DispatchTagStockDialog from '../components/DispatchTagStockDialog.vue'
import { useProductionDepartment } from '../composables/useProductionDepartment'
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
  dispatchDialogVisible, dispatchSubmitting, openDispatch, openWorkOrder,
  refresh, saveDispatch, saveWorkOrder, selectRepository,
  existingTagIds, applyingTagIds, setExistingTagFilter, setApplyingTagFilter,
  tagItems, tagLoading, submitting,
} = controller
const showSelectedWorkOrders = computed(() => Boolean(selectedRepository.value))
onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      :department-name="departmentName"
      :description="description"
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
          :allow-dispatch="mode === 'production'"
          @select="selectRepository"
          @create-work-order="openWorkOrder"
          @dispatch="openDispatch"
        />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total" :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-execution">
        <div class="production-card production-details">
          <div v-if="selectedRepository" class="production-selection">
            <strong>{{ selectedRepository.part_no === selectedRepository.part_name ? selectedRepository.part_name : `${selectedRepository.part_no} - ${selectedRepository.part_name}` }}</strong>
            <span>
              {{ selectedRepository.customer_order_no }} · {{ selectedRepository.procedure_name }}
              <template v-if="mode === 'production'"> · 相关标记工单</template>
              <template v-else> · 待到货</template>
            </span>
          </div>
          <WorkOrderCards
            v-if="showSelectedWorkOrders"
            :items="workOrders"
            :loading="detailLoading"
            :mode="mode"
            @submit="workOrderActions.submit"
            @submit-qc="workOrderActions.submitQc"
            @resubmit-qc="workOrderActions.resubmitQc"
            @cancel="workOrderActions.cancel"
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
    <DispatchTagStockDialog
      v-if="mode === 'production'"
      v-model="dispatchDialogVisible"
      :item="activeRepository"
      :tag-cards="tagItems"
      :submitting="dispatchSubmitting"
      @submit="saveDispatch"
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
}

@media (max-width: 760px) {
  .repository-filter-row {
    display: grid;
    grid-template-columns: 1fr;
  }
}
</style>
