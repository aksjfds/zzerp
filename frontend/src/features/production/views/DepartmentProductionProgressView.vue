<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import DepartmentProductionTaskTable from '../components/DepartmentProductionTaskTable.vue'
import ProductionProgressItemDrawer from '../components/ProductionProgressItemDrawer.vue'
import ProductionTaskWorkOrderDrawer from '../components/ProductionTaskWorkOrderDrawer.vue'
import {
  queryDepartmentProductionProgress,
} from '../api/productionProgress'
import type {
  DepartmentProductionProgressItem,
  ProductionTaskProcessingStatus,
} from '../domain/productionProgress'
import '../styles/workspace.css'

const props = withDefaults(defineProps<{
  embedded?: boolean
  departmentCode?: string
  departmentName?: string
  specialPrinting?: boolean
}>(), {
  embedded: false,
  departmentCode: '',
  departmentName: '生产部门',
  specialPrinting: false,
})
const emit = defineEmits<{
  createWorkOrder: [
    item: DepartmentProductionProgressItem,
    status: ProductionTaskProcessingStatus,
  ]
}>()
const route = useRoute()
const departmentCode = computed(
  () => String(props.departmentCode || route.meta.departmentCode || ''),
)
const items = ref<DepartmentProductionProgressItem[]>([])
const loading = ref(false)
const loadError = ref('')
let loadRevision = 0
const keyword = ref('')
const page = ref(1)
const pageSize = 50
const total = ref(0)
const selectedItem = ref<DepartmentProductionProgressItem | null>(null)
const detailVisible = ref(false)
const selectedWorkOrderItem = ref<DepartmentProductionProgressItem | null>(null)
const selectedWorkOrderStatus = ref<ProductionTaskProcessingStatus | null>(null)
const workOrderDrawerVisible = ref(false)


async function load() {
  if (!departmentCode.value) return
  const revision = ++loadRevision
  loading.value = true
  loadError.value = ''
  items.value = []
  try {
    const result = await queryDepartmentProductionProgress(
      departmentCode.value,
      page.value,
      pageSize,
      keyword.value.trim(),
    )
    if (revision !== loadRevision) return
    items.value = result.data
    total.value = result.total
  } catch (error) {
    if (revision === loadRevision) loadError.value = getApiErrorDetail(error)?.message || '生产任务加载失败'
  } finally {
    if (revision === loadRevision) loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function clear() {
  keyword.value = ''
  search()
}

function openDetail(item: DepartmentProductionProgressItem) {
  selectedItem.value = item
  detailVisible.value = true
}

function openWorkOrders(
  item: DepartmentProductionProgressItem,
  status: ProductionTaskProcessingStatus,
) {
  selectedWorkOrderItem.value = item
  selectedWorkOrderStatus.value = status
  workOrderDrawerVisible.value = true
}

function openAllWorkOrders(item: DepartmentProductionProgressItem) {
  selectedWorkOrderItem.value = item
  selectedWorkOrderStatus.value = null
  workOrderDrawerVisible.value = true
}

function createWorkOrder(
  item: DepartmentProductionProgressItem,
  status: ProductionTaskProcessingStatus,
) {
  emit('createWorkOrder', item, status)
}

defineExpose({ load })

onMounted(load)
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" :class="{ 'production-page': !embedded }">
    <DepartmentPageHeader
      v-if="!embedded"
      :department-name="departmentName"
      page-title="生产任务"
      description="生产计划确认后可查看本部门需要生产的配件或装配体。"
      @refresh="load"
    />

    <section class="progress-panel">
      <div class="progress-toolbar">
        <ElInput
          v-model="keyword"
          clearable
          placeholder="搜索物料编号、物料名称或订单号"
          @clear="search"
          @keyup.enter="search"
        />
        <ElButton type="primary" @click="search">查询</ElButton>
        <ElButton @click="clear">清空</ElButton>
      </div>

      <LoadErrorAlert v-if="loadError" :message="loadError" :loading="loading" @retry="load" />
      <DepartmentProductionTaskTable
        v-else
        :items="items"
        :loading="loading"
        @select="openDetail"
        @view-all-work-orders="openAllWorkOrders"
        @view-work-orders="openWorkOrders"
        @create-work-order="createWorkOrder"
      />

      <ElPagination
        v-if="!loadError"
        v-model:current-page="page"
        class="progress-pagination"
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="total"
        @current-change="load"
      />
    </section>

    <ProductionProgressItemDrawer
      v-model="detailVisible"
      :department-code="departmentCode"
      :item="selectedItem"
    />
    <ProductionTaskWorkOrderDrawer
      v-model="workOrderDrawerVisible"
      :department-code="departmentCode"
      :item="selectedWorkOrderItem"
      :status="selectedWorkOrderStatus"
      :special-printing="specialPrinting"
      @changed="load"
    />
  </component>
</template>

<style scoped>
.progress-panel {
  position: relative;
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: 6px;
  color: var(--erp-text);
  background: var(--erp-surface);
}

.progress-panel::before {
  position: absolute;
  top: -1px;
  left: 20px;
  width: 44px;
  height: 2px;
  background: var(--erp-primary);
  content: '';
  pointer-events: none;
}

.progress-toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 520px) max-content max-content;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--erp-border);
}

.progress-toolbar :deep(.el-button) {
  margin: 0;
}

.progress-pagination {
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--erp-border);
}

@media (max-width: 680px) {
  .progress-panel {
    padding: 14px;
  }

  .progress-toolbar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .progress-toolbar :deep(.el-input) {
    grid-column: 1 / -1;
  }

  .progress-toolbar :deep(.el-button) {
    width: 100%;
    margin: 0;
  }

  .progress-pagination {
    justify-content: center;
  }
}
</style>
