<script setup lang="ts">
import { computed, onMounted } from 'vue'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import RepositoryFilterBar from '../components/RepositoryFilterBar.vue'
import RepositoryCards from '../components/RepositoryCards.vue'
import TagCombinationCards from '../components/TagCombinationCards.vue'
import WorkOrderCards from '../components/WorkOrderCards.vue'
import CreateWorkOrderDialog from '../components/CreateWorkOrderDialog.vue'
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
  dispatchDialogVisible, dispatchSubmitting, openDispatch, openTagWorkOrder, openWorkOrder,
  refresh, saveDispatch, saveWorkOrder, selectRepository,
  selectedTag, selectedTagKey, selectTag, tagItems, tagLoading, submitting,
} = controller
const showSelectedWorkOrders = computed(() => (
  props.mode !== 'production'
  || (selectedTag.value?.tag_set_id !== null && selectedTag.value?.tag_set_id !== undefined)
))
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
          :allow-work-order="mode !== 'production'"
          :allow-dispatch="mode === 'production'"
          @select="selectRepository"
          @create-work-order="openWorkOrder"
          @dispatch="openDispatch"
        />
        <ElPagination v-model:current-page="repositoryPage" class="production-pagination" layout="prev, next, total" :page-size="pageSize" :total="repositoryTotal" @current-change="changeRepositoryPage" />
      </div>
      <div class="production-execution">
        <div v-if="mode === 'production'" class="production-card production-tags">
          <div v-if="selectedRepository" class="production-selection">
            <strong>标记组合</strong>
            <span>{{ selectedRepository.procedure_name }}</span>
          </div>
          <TagCombinationCards
            v-if="selectedRepository"
            :items="tagItems"
            :loading="tagLoading"
            :selected-key="selectedTagKey"
            @select="selectTag"
            @create-work-order="openTagWorkOrder"
          />
          <ElEmpty v-else description="请先选择配件" :image-size="64" />
        </div>
        <div class="production-card production-details">
          <div v-if="selectedRepository" class="production-selection">
            <strong>{{ selectedRepository.part_no === selectedRepository.part_name ? selectedRepository.part_name : `${selectedRepository.part_no} - ${selectedRepository.part_name}` }}</strong>
            <span>
              {{ selectedRepository.customer_order_no }} · {{ selectedRepository.procedure_name }}
              <template v-if="mode === 'production'"> · {{ selectedTag?.tag_set_name || '请选择标记组合' }}</template>
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
            :description="selectedRepository ? (selectedTag ? '未打标记是开单来源，没有对应目标工单' : '请选择标记组合查看工单') : '请先选择配件'"
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
      v-model="dialogVisible"
      :item="activeRepository"
      :sources="tagItems"
      :preferred-source-key="selectedTagKey"
      :workers="workers"
      :submitting="submitting"
      :mode="mode"
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
