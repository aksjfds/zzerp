<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryProductionProgress, type DepartmentWorkOrder, type ProgressProduct } from '../api/plans'
import DepartmentMovementDialog from './DepartmentMovementDialog.vue'

type ProgressRow = {
  key: string
  label: string
  kind: 'product' | 'material' | 'order'
  part_no?: string
  order?: DepartmentWorkOrder
  children?: ProgressRow[]
}
const products = ref<ProgressProduct[]>([])
const total = ref(0), page = ref(1), loading = ref(false), error = ref('')
const filters = reactive({ order_no: '', product_keyword: '' })
const movementOrder = ref<DepartmentWorkOrder | null>(null)
let active = true, revision = 0
const rows = computed<ProgressRow[]>(() => products.value.map(product => ({
  key: `product:${product.product_id}`, kind: 'product',
  label: `${product.factory_code} · ${product.product_name}`,
  children: product.materials.map(material => ({
    key: `product:${product.product_id}:material:${material.material_node_id}`,
    kind: 'material', label: material.part_name, part_no: material.part_no,
    children: material.work_orders.map(order => ({
      key: `order:${order.id}`, kind: 'order', label: order.department_name, order,
    })),
  })),
})))
const expandedProductKeys = computed(() => rows.value.map(row => row.key))
async function load() {
  const current = ++revision
  loading.value = true; error.value = ''; products.value = []
  try {
    const result = await queryProductionProgress({ page: page.value,
      order_no: filters.order_no.trim() || undefined,
      product_keyword: filters.product_keyword.trim() || undefined })
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value-1)*20) {
      page.value = Math.max(1, Math.ceil(result.total/20)); await load(); return
    }
    products.value = result.data; total.value = result.total
  } catch (cause) {
    if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '生产进度加载失败'
  } finally { if (active && current === revision) loading.value = false }
}
function search() { page.value = 1; void load() }
function clear() { Object.assign(filters, { order_no: '', product_keyword: '' }); search() }
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>

<template>
  <section>
    <ElForm inline @submit.prevent="search">
      <ElFormItem label="订单号"><ElInput v-model="filters.order_no" clearable maxlength="200" /></ElFormItem>
      <ElFormItem label="产品"><ElInput v-model="filters.product_keyword" clearable placeholder="厂编或产品名称" maxlength="200" /></ElFormItem>
      <ElFormItem><ElButton type="primary" native-type="submit">查询</ElButton><ElButton @click="clear">清空</ElButton><ElButton :loading="loading" @click="load">刷新</ElButton></ElFormItem>
    </ElForm>
    <p class="progress-note">产品 → 配件或装配体 → 部门工单。工单按订单分别沿正式流程排列；分支依图中顺序展示，回路从入口遍历，每张工单仅列一次。数量按各工单独立统计，装配体到料按实际物料分项显示。</p>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" row-key="key" :expand-row-keys="expandedProductKeys" border table-layout="auto" empty-text="暂无生产进度">
      <ElTableColumn prop="label" label="产品／配件或装配体／部门工单" min-width="330" />
      <ElTableColumn prop="part_no" label="配件／组成编号" min-width="180" />
      <ElTableColumn label="订单号" min-width="180"><template #default="{ row }">{{ row.order?.order_no || '—' }}</template></ElTableColumn>
      <ElTableColumn label="客户" min-width="140"><template #default="{ row }">{{ row.order?.customer_name || '—' }}</template></ElTableColumn>
      <ElTableColumn label="订单数量" width="110" align="right"><template #default="{ row }">{{ row.order?.order_quantity ?? '—' }}</template></ElTableColumn>
      <ElTableColumn label="任务数量" width="110" align="right"><template #default="{ row }">{{ row.order?.task_quantity ?? '—' }}</template></ElTableColumn>
      <ElTableColumn label="累积到料/累计出料" min-width="230"><template #default="{ row }">{{ row.order ? `${row.order.received_quantity}/${row.order.issued_quantity}` : '—' }}</template></ElTableColumn>
      <ElTableColumn label="查看" width="90" fixed="right"><template #default="{ row }"><ElButton v-if="row.order" link type="primary" @click="movementOrder = row.order">流水</ElButton></template></ElTableColumn>
    </ElTable>
    <p v-if="!error" class="progress-note">按产品分页，每页最多20个产品，页内包含所选订单范围的全部部门工单。</p>
    <ElPagination v-if="!error" v-model:current-page="page" :total="total" :page-size="20" layout="prev, pager, next, total" @current-change="load" />
    <DepartmentMovementDialog v-if="movementOrder" :key="movementOrder.id" :order="movementOrder" @close="movementOrder = null" />
  </section>
</template>

<style scoped>
.progress-note { color: var(--erp-text-secondary); font-size: 13px; line-height: 1.6; }
.el-pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
