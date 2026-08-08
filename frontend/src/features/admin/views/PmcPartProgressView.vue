<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import ProductionFlowViewer from '@/features/customer-orders/components/ProductionFlowViewer.vue'
import { queryCustomerOrderProduction } from '@/features/customer-orders/api/customerOrders'
import type { CustomerOrderProduction } from '@/features/customer-orders/domain/types'
import PartDepartmentProgressCell from '../components/PartDepartmentProgressCell.vue'
import { queryPmcPartProgress } from '../api/pmcPartProgress'
import type {
  PmcOrderPartProgress,
  PmcProgressDepartment,
} from '../domain/pmcPartProgress'

const route = useRoute()
const router = useRouter()
const orders = ref<PmcOrderPartProgress[]>([])
const departments = ref<PmcProgressDepartment[]>([])
const productionByOrder = reactive<Record<number, CustomerOrderProduction | undefined>>({})
const expandedOrderIds = ref<number[]>([])
const loadingFlowOrderIds = ref<number[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const filters = reactive({
  keyword: '',
  orderStatus: '',
  departmentCode: '',
  onlyException: false,
  onlyUnfinished: false,
})
const statusLabels: Record<string, string> = {
  draft: '草稿',
  confirmed: '已确认',
  planned: '生产中',
  cancelled: '已取消',
  closed: '已完成',
}
const statusTagTypes = {
  draft: 'info',
  confirmed: 'primary',
  planned: 'warning',
  cancelled: 'danger',
  closed: 'success',
} as const
const focusedOrderId = computed(() => {
  const value = Number(route.query.orderId)
  return Number.isInteger(value) && value > 0 ? value : undefined
})
const visibleDepartments = computed(() => filters.departmentCode
  ? departments.value.filter(item => item.department_code === filters.departmentCode)
  : departments.value)

function statusTagType(status: string) {
  return statusTagTypes[status as keyof typeof statusTagTypes] ?? 'info'
}

async function loadProduction(orderId: number) {
  if (productionByOrder[orderId] || loadingFlowOrderIds.value.includes(orderId)) return
  loadingFlowOrderIds.value.push(orderId)
  try {
    productionByOrder[orderId] = await queryCustomerOrderProduction(orderId)
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '订单生产流程加载失败')
  } finally {
    loadingFlowOrderIds.value = loadingFlowOrderIds.value.filter(id => id !== orderId)
  }
}

async function focusOrder(orderId: number) {
  if (!expandedOrderIds.value.includes(orderId)) {
    expandedOrderIds.value.push(orderId)
  }
  await loadProduction(orderId)
  await nextTick()
  document.getElementById(`pmc-order-${orderId}`)?.scrollIntoView({
    behavior: 'smooth',
    block: 'start',
  })
}

async function load() {
  loading.value = true
  try {
    const result = await queryPmcPartProgress({
      page: page.value,
      page_size: pageSize,
      keyword: filters.keyword.trim() || undefined,
      focus_order_id: focusedOrderId.value,
      order_status: filters.orderStatus || undefined,
      department_code: filters.departmentCode || undefined,
      only_exception: filters.onlyException || undefined,
      only_unfinished: filters.onlyUnfinished || undefined,
    })
    orders.value = result.data
    total.value = result.total
    departments.value = result.departments
    if (
      focusedOrderId.value
      && result.data.some(item => item.customer_order_id === focusedOrderId.value)
    ) {
      await focusOrder(focusedOrderId.value)
    }
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '配件生产进度加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

async function clear() {
  Object.assign(filters, {
    keyword: '',
    orderStatus: '',
    departmentCode: '',
    onlyException: false,
    onlyUnfinished: false,
  })
  page.value = 1
  if (focusedOrderId.value) {
    const query = { ...route.query }
    delete query.orderId
    await router.replace({ query })
    return
  }
  void load()
}

function toggleFlow(orderId: number) {
  if (expandedOrderIds.value.includes(orderId)) {
    expandedOrderIds.value = expandedOrderIds.value.filter(id => id !== orderId)
    return
  }
  expandedOrderIds.value.push(orderId)
  void loadProduction(orderId)
}

watch(
  () => route.query.orderId,
  () => {
    page.value = 1
    void load()
  },
)
onMounted(load)
defineExpose({ load })
</script>

<template>
  <section class="pmc-part-progress">
    <div class="progress-filters">
      <ElInput
        v-model="filters.keyword"
        clearable
        placeholder="搜索订单号、客户、厂编、产品或配件"
        @clear="search"
        @keyup.enter="search"
      />
      <ElSelect
        v-model="filters.orderStatus"
        placement="top-start"
        :fallback-placements="['top-start', 'top-end']"
        clearable
        placeholder="订单状态"
      >
        <ElOption label="草稿" value="draft" />
        <ElOption label="已确认" value="confirmed" />
        <ElOption label="生产中" value="planned" />
        <ElOption label="已完成" value="closed" />
        <ElOption label="已取消" value="cancelled" />
      </ElSelect>
      <ElSelect
        v-model="filters.departmentCode"
        placement="top-start"
        :fallback-placements="['top-start', 'top-end']"
        clearable
        placeholder="部门"
      >
        <ElOption
          v-for="department in departments"
          :key="department.department_code"
          :label="department.department_name"
          :value="department.department_code"
        />
      </ElSelect>
      <ElCheckbox v-model="filters.onlyUnfinished">仅未完成</ElCheckbox>
      <ElCheckbox v-model="filters.onlyException">仅异常</ElCheckbox>
      <ElButton type="primary" @click="search">查询</ElButton>
      <ElButton @click="clear">清空</ElButton>
    </div>

    <div v-loading="loading" class="order-progress-list">
      <ElEmpty v-if="!loading && !orders.length" description="暂无符合条件的订单配件" />
      <article
        v-for="order in orders"
        :id="`pmc-order-${order.customer_order_id}`"
        :key="order.customer_order_id"
        class="order-progress-card"
        :class="{ focused: focusedOrderId === order.customer_order_id }"
      >
        <header class="order-progress-header">
          <div>
            <span class="order-customer">{{ order.customer_name }}</span>
            <h2>订单 {{ order.customer_order_no }}</h2>
            <p>共 {{ order.parts.length }} 个生产配件</p>
          </div>
          <div class="order-actions">
            <ElTag :type="statusTagType(order.order_status)" effect="light">
              {{ statusLabels[order.order_status] || order.order_status }}
            </ElTag>
            <ElButton
              :loading="loadingFlowOrderIds.includes(order.customer_order_id)"
              @click="toggleFlow(order.customer_order_id)"
            >
              {{ expandedOrderIds.includes(order.customer_order_id) ? '收起生产流程' : '查看生产流程' }}
            </ElButton>
          </div>
        </header>

        <ElTable
          :data="order.parts"
          border
          table-layout="auto"
          class="progress-matrix"
          empty-text="该订单暂无符合条件的配件"
        >
          <ElTableColumn fixed label="配件" width="280">
            <template #default="{ row }">
              <strong>{{ row.part_display_name }}</strong>
              <p>{{ row.factory_code }} · {{ row.product_name }}</p>
            </template>
          </ElTableColumn>
          <ElTableColumn
            v-for="department in visibleDepartments"
            :key="department.department_code"
            :label="department.department_name"
            min-width="190"
          >
            <template #default="{ row }">
              <PartDepartmentProgressCell
                :item="row.departments[department.department_code]"
                :department-code="department.department_code"
              />
            </template>
          </ElTableColumn>
          <ElTableColumn label="需求" width="82" align="center">
            <template #default="{ row }">{{ row.target_quantity }}</template>
          </ElTableColumn>
          <ElTableColumn label="交期" width="112">
            <template #default="{ row }">{{ row.delivery_date }}</template>
          </ElTableColumn>
        </ElTable>

        <section
          v-if="expandedOrderIds.includes(order.customer_order_id)"
          v-loading="loadingFlowOrderIds.includes(order.customer_order_id)"
          class="order-production-flow"
        >
          <template v-if="productionByOrder[order.customer_order_id]?.products.length">
            <section
              v-for="productStatus in productionByOrder[order.customer_order_id]?.products"
              :key="productStatus.customer_order_item_id"
              class="product-flow"
            >
              <h3>
                {{ productStatus.factory_code }} · {{ productStatus.product_name }}
                · 订单数量 {{ productStatus.order_quantity }}
              </h3>
              <ProductionFlowViewer
                :flow="productStatus.process_flow"
                :stats="productStatus.node_stats"
                :edge-stats="productStatus.edge_stats"
              />
            </section>
          </template>
          <ElEmpty
            v-else-if="!loadingFlowOrderIds.includes(order.customer_order_id)"
            description="该订单尚未生成生产流程"
          />
        </section>
      </article>
    </div>

    <ElPagination
      v-model:current-page="page"
      class="progress-pagination"
      layout="prev, pager, next, total"
      :page-size="pageSize"
      :total="total"
      @current-change="load"
    />
  </section>
</template>

<style scoped>
.pmc-part-progress {
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-sm);
}
.progress-filters {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 150px 160px auto auto auto auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}
.order-progress-list { min-height: 160px; }
.order-progress-card {
  scroll-margin-top: 16px;
  overflow: hidden;
  margin-bottom: 18px;
  border: 1px solid var(--erp-border);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
}
.order-progress-card.focused {
  border-color: var(--erp-primary);
  box-shadow: 0 0 0 2px var(--md-primary-container);
}
.order-progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  background: var(--md-surface-container-low);
}
.order-customer { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.order-progress-header h2 { margin: 4px 0; font-size: 18px; }
.order-progress-header p { margin: 0; color: var(--el-text-color-secondary); font-size: 12px; }
.order-actions { display: flex; align-items: center; gap: 10px; }
.progress-matrix { border-right: 0; border-left: 0; }
.progress-matrix :deep(.el-table__cell) { vertical-align: top; }
.progress-matrix strong { font-size: 13px; }
.progress-matrix p { margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
.order-production-flow {
  min-height: 120px;
  padding: 18px;
  border-top: 1px solid var(--erp-border);
  background: var(--md-surface-container-low);
}
.product-flow + .product-flow { margin-top: 24px; }
.product-flow h3 { margin: 0 0 12px; font-size: 15px; }
.progress-pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 1100px) {
  .progress-filters { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 680px) {
  .pmc-part-progress { padding: 12px; border-radius: var(--erp-radius); }
  .progress-filters { grid-template-columns: 1fr; }
  .progress-filters :deep(.el-button) { width: 100%; margin: 0; }
  .order-progress-header { align-items: flex-start; flex-direction: column; }
  .order-actions { justify-content: space-between; width: 100%; }
}
</style>
