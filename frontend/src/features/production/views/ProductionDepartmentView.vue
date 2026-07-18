<script setup lang="ts">
import { onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import SubstepCards from '../components/SubstepCards.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import DispatchStageStockDialog from '../components/DispatchStageStockDialog.vue'
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
  activeSubstepSource, dispatchDialogVisible, dispatchSubmitting,
  openDispatch, openSubstepWorkOrder, openWorkOrder,
  refresh, saveDispatch, saveWorkOrder,
  selectRepository, selectedSubstep, selectedSubstepKey, selectSubstep,
  substepItems, substepLoading, submitting,
} = controller
onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader :department-name="departmentName" :description="description" @refresh="refresh" />
    <RepositoryFilterBar @search="applyFilters" />
    <section class="production-workspace">
      <div class="production-card">
        <RepositoryCards
          :items="items"
          :loading="loading"
          :selected-key="selectedCardKey"
          :mode="mode"
          :allow-work-order="mode === 'purchase'"
          :allow-dispatch="mode === 'production'"
          @select="selectRepository"
          @create-work-order="openWorkOrder"
          @dispatch="openDispatch"
        />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total" :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-execution">
        <div v-if="mode === 'production'" class="production-card production-substeps">
          <div v-if="selectedRepository" class="production-selection">
            <strong>细分状态</strong>
            <span>{{ selectedRepository.procedure_name }}</span>
          </div>
          <SubstepCards
            v-if="selectedRepository"
            :items="substepItems"
            :loading="substepLoading"
            :procedure-name="selectedRepository?.procedure_name"
            :selected-key="selectedSubstepKey"
            @select="selectSubstep"
            @create-work-order="openSubstepWorkOrder"
          />
          <ElEmpty v-else description="请先选择配件" :image-size="64" />
        </div>
        <div class="production-card production-details">
          <div v-if="selectedRepository" class="production-selection">
            <strong>{{ selectedRepository.part_no === selectedRepository.part_name ? selectedRepository.part_name : `${selectedRepository.part_no} - ${selectedRepository.part_name}` }}</strong>
            <span>
              {{ selectedRepository.customer_order_no }} · {{ selectedRepository.procedure_name }}
              <template v-if="mode === 'production'"> · {{ selectedSubstep?.substep_name || (selectedSubstep ? `未${selectedRepository.procedure_name}` : '请选择细分') }}</template>
              <template v-else> · {{ selectedRepository.current_stage_name || '待加工' }}</template>
            </span>
          </div>
          <WorkOrderCards
            v-if="mode !== 'production' || (selectedSubstep && selectedSubstep.substep_id !== null)"
            :items="workOrders"
            :loading="detailLoading"
            :mode="mode"
            @submit="workOrderActions.submit"
            @submit-qc="workOrderActions.submitQc"
            @cancel="workOrderActions.cancel"
          />
          <ElEmpty
            v-else
            :description="selectedRepository ? '请选择具体细分查看工单' : '请先选择配件'"
            :image-size="64"
          />
          <ElPagination
            v-if="mode !== 'production' || (selectedSubstep && selectedSubstep.substep_id !== null)"
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
      v-model="dialogVisible"
      :item="activeRepository"
      :source="activeSubstepSource"
      :workers="workers"
      :submitting="submitting"
      :mode="mode"
      @submit="saveWorkOrder"
    />
    <DispatchStageStockDialog
      v-if="mode === 'production'"
      v-model="dispatchDialogVisible"
      :item="activeRepository"
      :substeps="substepItems"
      :submitting="dispatchSubmitting"
      @submit="saveDispatch"
    />
  </main>
</template>
