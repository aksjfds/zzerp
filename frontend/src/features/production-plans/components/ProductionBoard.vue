<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { queryProductionDepartments, type ProductionDepartment } from '@/features/production-departments'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryProductionProgress, queryDepartmentWorkOrders, type ProgressPlan, type ProgressProduct, type DepartmentWorkOrder, type WorkOrderSchedule } from '../api/plans'
import WorkOrderProgressCard from './WorkOrderProgressCard.vue'
import DepartmentMovementDialog from './DepartmentMovementDialog.vue'

const departments = ref<ProductionDepartment[]>([]), department = ref('')
const plans = ref<ProgressPlan[]>([]), orders = ref<DepartmentWorkOrder[]>([])
const orderNo = ref(''), product = ref(''), page = ref(1), total = ref(0), loading = ref(false), error = ref('')
const selected = ref<{ plan: ProgressPlan; product: ProgressProduct }>()
const ledger = ref<DepartmentWorkOrder>()
const pageSize = computed(() => department.value ? 50 : 20)
const statuses = { draft: '草稿', confirmed: '已确认', cancelled: '已取消', completed: '已完成' }
function applySchedule(updates: WorkOrderSchedule[]) {
  const byId = new Map(updates.map(item => [item.id, item]))
  const visibleOrders = [...orders.value, ...plans.value.flatMap(plan => plan.products.flatMap(item => item.materials.flatMap(material => material.work_orders)))]
  for (const order of visibleOrders) {
    const update = byId.get(order.id)
    if (update) Object.assign(order, update)
  }
}
function statusLabel(item: ProgressProduct) {
  const status = item.materials[0]?.work_orders[0]?.plan_status
  return status ? statuses[status] : '—'
}
function percent(item: ProgressProduct) {
  const done = BigInt(item.completed_quantity), target = BigInt(item.task_quantity)
  return Number((done < target ? done : target) * 10000n / target) / 100
}
let active = true, revision = 0, departmentRevision = 0
async function load() {
  const current = ++revision; loading.value = true; error.value = ''; plans.value = []; orders.value = []; selected.value = undefined
  const filters = { page: page.value, order_no: orderNo.value.trim() || undefined, product_keyword: product.value.trim() || undefined }
  try {
    if (department.value) {
      const result = await queryDepartmentWorkOrders({ ...filters, department_code: department.value })
      if (!active || current !== revision) return
      orders.value = result.data; total.value = result.total
    } else {
      const result = await queryProductionProgress(filters)
      if (!active || current !== revision) return
      plans.value = result.data; total.value = result.total
    }
    if (page.value > 1 && total.value <= (page.value - 1) * pageSize.value) { page.value = Math.max(1, Math.ceil(total.value / pageSize.value)); await load() }
  } catch (cause) { if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '生产看板加载失败' }
  finally { if (active && current === revision) loading.value = false }
}
function search() { page.value = 1; void load() }
async function initialize() {
  const current = ++departmentRevision
  loading.value = true
  try {
    const result = await queryProductionDepartments()
    if (!active || current !== departmentRevision) return
    departments.value = result.filter(item => !item.is_warehouse)
    await load()
  } catch (cause) { if (active && current === departmentRevision) { error.value = getApiErrorDetail(cause)?.message || '部门加载失败'; loading.value = false } }
}
onMounted(initialize)
onBeforeUnmount(() => { active = false; revision += 1; departmentRevision += 1 })
</script>
<template>
  <section class="production-board">
    <ElForm class="query-toolbar" inline label-position="top" @submit.prevent="search">
      <ElFormItem label="订单号"><ElInput v-model="orderNo" clearable maxlength="200" /></ElFormItem>
      <ElFormItem label="产品"><ElInput v-model="product" clearable maxlength="200" /></ElFormItem>
      <ElFormItem><ElButton type="primary" native-type="submit">查询</ElButton><ElButton :loading="loading" @click="initialize">刷新看板</ElButton></ElFormItem>
    </ElForm>
    <ElTabs v-model="department" class="department-tabs" @tab-change="search"><ElTabPane label="全部订单" name="" /><ElTabPane v-for="item in departments" :key="item.code" :label="item.name" :name="item.code" /></ElTabs>
    <LoadErrorAlert :message="error" :loading="loading" @retry="initialize" />
    <div v-if="!error" v-loading="loading">
      <ElEmpty v-if="!loading && !(department ? orders.length : plans.length)" description="暂无生产任务" />
      <div v-if="department" class="route-list"><WorkOrderProgressCard v-for="order in orders" :key="order.id" :order="order" department-view @ledger="ledger = $event" @scheduled="applySchedule" /></div>
      <div v-else>
        <section v-for="plan in plans" :key="plan.production_plan_id" class="order-group">
          <header class="order-group-heading"><strong>{{ plan.order_no }}</strong><span>{{ plan.customer_name }}</span></header>
          <div class="route-list"><article v-for="item in plan.products" :key="item.product_id" class="order-card">
            <div><h3>{{ item.factory_code }} · {{ item.product_name }}</h3><p class="order-meta">订单数量 {{ item.order_quantity }} · {{ item.materials.length }} 项配件/装配体</p></div>
            <div><div class="order-quantity"><span>成品完成</span><strong>{{ item.completed_quantity }} <small>/ {{ item.task_quantity }}</small></strong></div><ElProgress :percentage="percent(item)" :stroke-width="8" color="var(--erp-success)" :format="() => `${item.completed_quantity}件`" /></div>
            <footer><ElTag type="info">{{ statusLabel(item) }}</ElTag><ElButton type="primary" plain @click="selected = { plan, product: item }">查看生产路线</ElButton></footer>
          </article></div>
        </section>
      </div>
    </div>
    <ElPagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next, total" @current-change="load" />
    <ElDrawer :model-value="!!selected" :title="selected ? `${selected.plan.order_no} · ${selected.product.factory_code} · ${selected.product.product_name}` : '生产路线'" size="min(1120px, 96vw)" @close="selected = undefined">
      <template v-if="selected"><section v-for="material in selected.product.materials" :key="material.material_node_id" class="material-section"><h3>{{ material.part_no }} · {{ material.part_name }}</h3><p>任务数量 {{ material.task_quantity }}</p><div class="route-list"><WorkOrderProgressCard v-for="order in material.work_orders" :key="order.id" :order="order" :scheduling-orders="material.work_orders" compact @ledger="ledger = $event" @scheduled="applySchedule" /></div></section></template>
    </ElDrawer>
    <DepartmentMovementDialog v-if="ledger" :key="ledger.id" :order="ledger" @close="ledger = undefined" />
  </section>
</template>
<style scoped>
.route-list { display: grid; grid-template-columns: minmax(0,1fr); gap: 10px; }
.order-card { display: grid; grid-template-columns: minmax(0,1.2fr) minmax(200px,1fr) auto; align-items: center; gap: 24px; min-width: 0; padding: 12px 18px; border: 1px solid var(--erp-border); border-radius: 10px; background: var(--erp-surface); }
.order-group { margin-bottom: 28px; }.order-group-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; padding: 12px 0; margin-bottom: 10px; border-bottom: 1px solid var(--erp-border); }.order-group-heading strong { font-size: 20px; color: var(--erp-primary-strong); }.order-group-heading span { color: var(--erp-text-secondary); }
.order-card h3 { margin: 0; font-size: 16px; }.order-card .order-meta { margin: 6px 0 0; }.order-card .order-quantity { margin-bottom: 8px; }.order-card .order-quantity strong { font-size: 21px; }
.order-card header, .order-card footer { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; }
.order-card header { overflow-wrap: anywhere; }.order-card header strong { color: var(--erp-primary-strong); font-size: 17px; }.order-card header span, .order-meta { color: var(--erp-text-secondary); font-size: 13px; }
h3 { margin: 18px 0; font-size: 18px; overflow-wrap: anywhere; }.order-quantity { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 14px; }.order-quantity > span { font-size: 13px; color: var(--erp-text-secondary); }.order-quantity strong { font-size: 26px; }.order-quantity small { font-size: 14px; color: var(--erp-text-secondary); font-weight: 500; }
.order-card footer { padding: 0; margin: 0; }.material-section { margin-bottom: 28px; }.material-section > p { color: var(--erp-text-secondary); }.el-pagination { margin-top: 24px; }
@media (max-width: 900px) { .order-card { grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: 14px; }.order-card footer { grid-column: 1 / -1; } }
@media (max-width: 520px) { .order-card { grid-template-columns: minmax(0,1fr); } }
</style>
