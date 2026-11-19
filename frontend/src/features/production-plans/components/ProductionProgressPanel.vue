<script setup lang="ts">
import { useCompactViewport } from '@/shared/layout/useCompactViewport'

import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { PLAN_PERMISSIONS } from '@/permission/constants'
import { useAuthStore } from '@/stores/auth'
import WorkOrderScheduleDialog from './WorkOrderScheduleDialog.vue'
import WorkOrderScheduleCell from './WorkOrderScheduleCell.vue'
import { queryProductionProgress, type DepartmentWorkOrder, type ProgressPlan, type WorkOrderSchedule } from '../api/plans'
import DepartmentMovementDialog from './DepartmentMovementDialog.vue'

const compact = useCompactViewport()
const auth = useAuthStore()
const scheduleOrder = ref<DepartmentWorkOrder>()
const scheduleOrders = ref<DepartmentWorkOrder[]>([])
function applyScheduleUpdates(updates: WorkOrderSchedule[]) {
  const byId = new Map(updates.map(item => [item.id, item]))
  for (const plan of plans.value) for (const product of plan.products) for (const material of product.materials) {
    for (const order of material.work_orders) {
      const update = byId.get(order.id)
      if (update) Object.assign(order, update)
    }
  }
}
function scheduleSaved(updates: WorkOrderSchedule[]) {
  applyScheduleUpdates(updates)
  scheduleOrder.value = undefined
}
type ProgressRow = {
  key: string
  label: string
  part_no?: string
  completed_quantity?: string
  completion_percent?: number
  order_quantity?: number
  task_quantity?: number
  schedulingOrders?: DepartmentWorkOrder[]
  order?: DepartmentWorkOrder
  children?: ProgressRow[]
}
const plans = ref<ProgressPlan[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const filters = reactive({ order_no: '', product_keyword: '' })
const movementOrder = ref<DepartmentWorkOrder | null>(null)
let active = true
let revision = 0
function completionPercent(quantity: string, target: number) {
  const completed = BigInt(quantity), total = BigInt(target)
  return Number((completed < total ? completed : total) * 10000n / total) / 100
}
const tables = computed(() => plans.value.map(plan => {
  const rows: ProgressRow[] = plan.products.map(product => ({
    key: `product:${product.product_id}`,
    label: `${product.factory_code} · ${product.product_name}`,
    completed_quantity: product.completed_quantity,
    completion_percent: completionPercent(product.completed_quantity, product.task_quantity),
    order_quantity: product.order_quantity, task_quantity: product.task_quantity,
    children: product.materials.map(material => ({
      key: `product:${product.product_id}:material:${material.material_node_id}`,
      label: material.part_name, part_no: material.part_no,
      order_quantity: material.order_quantity, task_quantity: material.task_quantity,
      children: material.work_orders.map(order => ({
        key: `order:${order.id}`, label: order.department_name, order, schedulingOrders: material.work_orders,
      })),
    })),
  }))
  return { ...plan, rows, expandedProductKeys: rows.map(row => row.key) }
}))
async function load() {
  const current = ++revision
  loading.value = true
  error.value = ''
  plans.value = []
  try {
    const result = await queryProductionProgress({
      page: page.value,
      order_no: filters.order_no.trim() || undefined,
      product_keyword: filters.product_keyword.trim() || undefined,
    })
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 20) {
      page.value = Math.max(1, Math.ceil(result.total / 20))
      await load()
      return
    }
    plans.value = result.data
    total.value = result.total
  } catch (cause) {
    if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '生产进度加载失败'
  } finally { if (active && current === revision) loading.value = false }
}
function search() {
  page.value = 1
  void load()
}
function clear() {
  Object.assign(filters, { order_no: '', product_keyword: '' })
  search()
}
onMounted(load)
onBeforeUnmount(() => {
  active = false
  revision += 1
})
</script>

<template>
  <section>
    <ElForm class="query-toolbar" label-position="top" inline @submit.prevent="search">
      <ElFormItem label="订单号"><ElInput v-model="filters.order_no" clearable maxlength="200" /></ElFormItem>
      <ElFormItem label="产品"><ElInput v-model="filters.product_keyword" clearable placeholder="厂编或产品名称" maxlength="200" /></ElFormItem>
      <ElFormItem><ElButton type="primary" native-type="submit">查询</ElButton><ElButton @click="clear">清空</ElButton><ElButton :loading="loading" @click="load">刷新</ElButton></ElFormItem>
    </ElForm>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <div v-if="!error" v-loading="loading">
    <ElEmpty v-if="!loading && !tables.length" />
    <section v-for="table in tables" :key="table.production_plan_id" class="order-progress" :aria-label="`订单 ${table.order_no}`">
    <header class="order-heading"><div><span>客户订单</span><h3>{{ table.order_no }}</h3></div><span>{{ table.customer_name }}</span><ElTag type="info">{{ table.rows.length }} 项产品</ElTag></header>
    <ElTable :data="table.rows" row-key="key" :expand-row-keys="table.expandedProductKeys" :row-class-name="({ row }: { row: ProgressRow }) => row.completed_quantity !== undefined ? 'progress-product-row' : ''" table-layout="auto" empty-text="暂无生产进度">
      <ElTableColumn class-name="data-primary" prop="label" label="产品／配件或装配体／部门工单" min-width="330" />
      <ElTableColumn label="配件／组成编号" min-width="180">
        <template #default="{ row }">
          <ElProgress v-if="row.completed_quantity !== undefined" class="product-completion" :percentage="row.completion_percent" :stroke-width="26" text-inside color="var(--erp-success-indicator)" :aria-label="`完成 ${row.completed_quantity}，目标 ${row.task_quantity}`">
            <span>完成 {{ row.completed_quantity }}</span>
          </ElProgress>
          <span v-else>{{ row.part_no }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="订单数量" width="110" align="right"><template #default="{ row }"><span>{{ row.order_quantity ?? '' }}</span></template></ElTableColumn>
      <ElTableColumn class-name="data-metric" label="任务数量" width="110" align="right"><template #default="{ row }"><span>{{ row.task_quantity ?? '' }}</span></template></ElTableColumn>
      <ElTableColumn class-name="data-metric" label="累积到料/累计出料" min-width="230"><template #default="{ row }"><span>{{ row.order ? `${row.order.received_quantity}/${row.order.issued_quantity}` : '' }}</span></template></ElTableColumn>
      <ElTableColumn label="交料日期" min-width="290"><template #default="{ row }">
        <WorkOrderScheduleCell v-if="row.order" :order="row.order" :orders="row.schedulingOrders"
          :editable="row.order.plan_status === 'confirmed' && !auth.user?.department_code && auth.hasPermission(PLAN_PERMISSIONS.edit)"
          @edit="scheduleOrders = row.schedulingOrders; scheduleOrder = row.order" @saved="applyScheduleUpdates" />
      </template></ElTableColumn>
      <ElTableColumn label="查看" width="90" :fixed="compact ? false : 'right'"><template #default="{ row }"><ElButton v-if="row.order" link type="primary" @click="movementOrder = row.order">流水</ElButton></template></ElTableColumn>
    </ElTable>
    </section>
    </div>
    <ElPagination v-if="!error" v-model:current-page="page" :total="total" :page-size="20" layout="prev, pager, next, total" @current-change="load" />
    <WorkOrderScheduleDialog v-if="scheduleOrder" :key="scheduleOrder.id" :order="scheduleOrder" :orders="scheduleOrders" @close="scheduleOrder = undefined" @saved="scheduleSaved" />
    <DepartmentMovementDialog v-if="movementOrder" :key="movementOrder.id" :order="movementOrder" @close="movementOrder = null" />
  </section>
</template>

<style scoped>

.el-pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.order-progress :deep(.progress-product-row td.data-primary .cell) { font-size: 16px; font-weight: 700; }
.product-completion { min-width: 150px; }
.product-completion :deep(.el-progress-bar__innerText) { position: absolute; left: 8px; top: 0; margin: 0; color: #052e16; font-weight: 600; line-height: 26px; }
.order-progress { min-width: 0; margin: 24px 0; padding: 16px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); }
.order-progress h3 { margin: 0 0 12px; font-size: 20px; font-weight: 600; line-height: 1.4; overflow-wrap: anywhere; }
.order-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; margin-bottom: 20px; }.order-heading > div { margin-right: auto; }.order-heading > div > span { font-size: 11px; color: var(--erp-text-muted); }.order-heading h3 { margin: 4px 0 0; }.order-heading > span { color: var(--erp-text-secondary); font-size: 14px; }

</style>
