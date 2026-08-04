<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import DepartmentSectionTabs from '../components/DepartmentSectionTabs.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import TagProductionOverview from '../components/TagProductionOverview.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
import PurchaseWorkOrderDialog from '../components/PurchaseWorkOrderDialog.vue'
import { useProductionDepartment } from '../composables/useProductionDepartment'
import { workOrderProductionOverview } from '../domain/productionOverview'
import { departmentSupports } from '@/features/departments/registry'
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
  repositoryPage, repositoryTotal, selectedRepository, selectedCardKey, workers, workshops,
} = workspace
const { items: workOrders, loading: detailLoading, page: historyPage, total: historyTotal } = workOrderList
const {
  activeRepository, applyFilters, changeRepositoryPage, dialogVisible, load, loadDetails,
  openWorkOrder, reloadWorkspace, refresh, saveWorkOrder, selectRepository,
  tagItems, tagLoading, submitting,
} = controller
const showSelectedWorkOrders = computed(() => Boolean(selectedRepository.value))
const nonTagOverview = computed(() => workOrderProductionOverview(
  workOrders.value,
  selectedRepository.value?.available_quantity ?? 0,
))
const supportsSpecialPrinting = computed(() => (
  departmentSupports(props.departmentCode, 'special_printing')
))
onMounted(load)
</script>

<template>
  <main class="production-page">
    <DepartmentPageHeader
      :department-name="departmentName"
      :description="description"
      @refresh="refresh"
    />
    <DepartmentSectionTabs
      :department-code="departmentCode"
      @configuration-saved="reloadWorkspace"
    >
    <RepositoryFilterBar
      :workshops="workshops"
      @search="applyFilters"
    />
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
          :special-printing="supportsSpecialPrinting"
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
    </DepartmentSectionTabs>
  </main>
</template>
