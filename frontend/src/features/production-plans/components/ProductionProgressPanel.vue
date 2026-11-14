<script setup lang="ts">
import { useCompactViewport } from '@/shared/layout/useCompactViewport'

import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryProductionProgress, type DepartmentWorkOrder, type ProgressPlan } from '../api/plans'
import DepartmentMovementDialog from './DepartmentMovementDialog.vue'

const compact = useCompactViewport()
type ProgressRow = {
  key: string
  label: string
  part_no?: string
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
const tables = computed(() => plans.value.map(plan => {
  const rows: ProgressRow[] = plan.products.map(product => ({
    key: `product:${product.product_id}`,
    label: `${product.factory_code} · ${product.product_name}`,
    children: product.materials.map(material => ({
      key: `product:${product.product_id}:material:${material.material_node_id}`,
      label: material.part_name, part_no: material.part_no,
      children: material.work_orders.map(order => ({
        key: `order:${order.id}`, label: order.department_name, order,
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
    <ElForm inline @submit.prevent="search">
      <ElFormItem label="订单号"><ElInput v-model="filters.order_no" clearable maxlength="200" /></ElFormItem>
      <ElFormItem label="产品"><ElInput v-model="filters.product_keyword" clearable placeholder="厂编或产品名称" maxlength="200" /></ElFormItem>
      <ElFormItem><ElButton type="primary" native-type="submit">查询</ElButton><ElButton @click="clear">清空</ElButton><ElButton :loading="loading" @click="load">刷新</ElButton></ElFormItem>
    </ElForm>
    <p class="progress-note">每个订单独立展示：产品 → 配件或装配体 → 部门工单。部门工单沿正式流程排列；分支依图中顺序展示，回路从入口遍历，每张工单仅列一次。装配体到料按实际物料分项显示。</p>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <div v-if="!error" v-loading="loading">
    <ElEmpty v-if="!loading && !tables.length" description="暂无生产进度" />
    <section v-for="table in tables" :key="table.production_plan_id" class="order-progress" :aria-label="`订单 ${table.order_no}`">
    <h3>{{ table.customer_name }} · 订单 {{ table.order_no }}</h3>
    <ElTable :data="table.rows" row-key="key" :expand-row-keys="table.expandedProductKeys" border table-layout="auto" empty-text="暂无生产进度">
      <ElTableColumn prop="label" label="产品／配件或装配体／部门工单" min-width="330" />
      <ElTableColumn prop="part_no" label="配件／组成编号" min-width="180" />
      <ElTableColumn label="订单数量" width="110" align="right"><template #default="{ row }">{{ row.order?.order_quantity ?? '—' }}</template></ElTableColumn>
      <ElTableColumn label="任务数量" width="110" align="right"><template #default="{ row }">{{ row.order?.task_quantity ?? '—' }}</template></ElTableColumn>
      <ElTableColumn label="累积到料/累计出料" min-width="230"><template #default="{ row }">{{ row.order ? `${row.order.received_quantity}/${row.order.issued_quantity}` : '—' }}</template></ElTableColumn>
      <ElTableColumn label="查看" width="90" :fixed="compact ? false : 'right'"><template #default="{ row }"><ElButton v-if="row.order" link type="primary" @click="movementOrder = row.order">流水</ElButton></template></ElTableColumn>
    </ElTable>
    </section>
    </div>
    <p v-if="!error" class="progress-note">按订单分页，每页最多20个订单，每个表格只展示该订单在筛选范围内的产品及全部部门工单。</p>
    <ElPagination v-if="!error" v-model:current-page="page" :total="total" :page-size="20" layout="prev, pager, next, total" @current-change="load" />
    <DepartmentMovementDialog v-if="movementOrder" :key="movementOrder.id" :order="movementOrder" @close="movementOrder = null" />
  </section>
</template>

<style scoped>
.progress-note { color: var(--erp-text-secondary); font-size: 13px; line-height: 1.6; }
.el-pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.order-progress { min-width: 0; margin: 20px 0; }
.order-progress h3 { margin: 0 0 12px; font-size: 16px; overflow-wrap: anywhere; }
</style>
