<script setup lang="ts">
import { useCompactViewport } from '@/shared/layout/useCompactViewport'

import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { useAuthStore } from '@/stores/auth'
import { DEPARTMENT_WORK_ORDER_OPERATE } from '@/permission/constants'
import DepartmentMovementDialog from './DepartmentMovementDialog.vue'
import HandoffTicketsPanel from './HandoffTicketsPanel.vue'
import { queryProductionDepartments, type ProductionDepartment } from '@/features/production-departments'
import { queryDepartmentWorkOrders, type DepartmentWorkOrder, type WorkOrderComponent } from '../api/plans'

const compact = useCompactViewport()
const props = defineProps<{ planId?: number; departmentCode?: string; canReceive?: boolean }>()
const authStore = useAuthStore()
const movementOrder = ref<DepartmentWorkOrder | null>(null)
const movementDirection = ref<'receipt' | 'issue'>()
const movementComponent = ref<WorkOrderComponent>()
const ticketsPanel = ref<InstanceType<typeof HandoffTicketsPanel>>()
function movementChanged() { void load(); void ticketsPanel.value?.refresh() }
function canOperate(order: DepartmentWorkOrder) {
  return authStore.user?.department_code === order.department_code
    && authStore.hasPermission(DEPARTMENT_WORK_ORDER_OPERATE)
}
function openMovement(order: DepartmentWorkOrder, direction?: 'receipt' | 'issue', component?: WorkOrderComponent) {
  movementOrder.value = order
  movementDirection.value = direction
  movementComponent.value = component
}
const departments = ref<ProductionDepartment[]>([])
const rows = ref<DepartmentWorkOrder[]>([])
type WorkOrderRow = DepartmentWorkOrder & { row_key: string; component?: WorkOrderComponent; children?: WorkOrderRow[] }
const tableRows = computed<WorkOrderRow[]>(() => rows.value.map(order => ({
  ...order, row_key: `order:${order.id}`,
  children: order.components.length ? order.components.map(component => ({
    ...order, row_key: `order:${order.id}:part:${component.material_node_id}`, component,
  })) : undefined,
})))
const hasComponents = computed(() => rows.value.some(order => order.components.length > 0))
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const departmentError = ref('')
const departmentLoading = ref(false)
const filters = reactive({ department_code: '', order_no: '', product_keyword: '' })
let active = true
let revision = 0

async function loadDepartments() {
  departmentLoading.value = true
  departmentError.value = ''
  try {
    const result = await queryProductionDepartments()
    if (active) departments.value = result
  } catch (cause) {
    if (active) departmentError.value = getApiErrorDetail(cause)?.message || '生产部门加载失败'
  } finally { if (active) departmentLoading.value = false }
}
async function load() {
  const current = ++revision
  rows.value = []
  loading.value = true
  error.value = ''
  try {
    const result = await queryDepartmentWorkOrders({
      page: page.value, department_code: props.departmentCode || filters.department_code || undefined,
      plan_id: props.planId, order_no: filters.order_no.trim() || undefined,
      product_keyword: filters.product_keyword.trim() || undefined,
    })
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 50) {
      page.value = Math.max(1, Math.ceil(result.total / 50))
      await load()
      return
    }
    rows.value = result.data
    total.value = result.total
  } catch (cause) {
    if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '部门生产安排加载失败'
  } finally { if (active && current === revision) loading.value = false }
}
function search() { page.value = 1; void load() }
function clear() {
  Object.assign(filters, { department_code: '', order_no: '', product_keyword: '' })
  search()
}
onMounted(() => { if (!props.departmentCode) void loadDepartments(); void load() })
watch(() => props.departmentCode, search)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>

<template>
  <section>
    <LoadErrorAlert :message="departmentError" :loading="departmentLoading" @retry="loadDepartments" />
    <ElForm inline @submit.prevent="search">
      <ElFormItem v-if="!departmentCode" label="部门"><ElSelect v-model="filters.department_code" clearable placeholder="全部部门" :loading="departmentLoading" :disabled="departmentLoading || !!departmentError" style="width: 150px"><ElOption v-for="department in departments" :key="department.code" :label="department.name" :value="department.code" /></ElSelect></ElFormItem>
      <ElFormItem label="订单号"><ElInput v-model="filters.order_no" clearable maxlength="200" /></ElFormItem>
      <ElFormItem label="产品"><ElInput v-model="filters.product_keyword" clearable placeholder="厂编或产品名称" maxlength="200" /></ElFormItem>
      <ElFormItem><ElButton type="primary" native-type="submit">查询</ElButton><ElButton @click="clear">清空</ElButton></ElFormItem>
    </ElForm>
    <LoadErrorAlert v-if="error" :message="error" :loading="loading" @retry="load" />
    <p v-if="hasComponents" class="tree-note">装配体展开后可按配件登记和查看到料。配件需求按当前 BOM 计算，仅统计该配件直接到料；整套或嵌套装配体到料请查看一级流水。出料统一在装配体登记。</p>
    <ElTable v-if="!error" v-table-column-widths="'planning.department-work-orders'" v-loading="loading" :data="tableRows" row-key="row_key" default-expand-all border stripe table-layout="auto" empty-text="暂无部门生产安排">
      <ElTableColumn label="配件／装配体名称" min-width="240"><template #default="{ row }">{{ row.component?.part_name ?? row.part_name }}</template></ElTableColumn>
      <ElTableColumn prop="order_no" label="订单号" min-width="160" />
      <ElTableColumn prop="department_name" label="部门" min-width="100" />
      <ElTableColumn prop="customer_name" label="客户" min-width="130" />
      <ElTableColumn label="产品" min-width="220"><template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template></ElTableColumn>
      <ElTableColumn label="配件／组成编号" min-width="150"><template #default="{ row }">{{ row.component?.part_no ?? row.part_no }}</template></ElTableColumn>
      <ElTableColumn prop="order_quantity" label="订单数量" width="110" align="right" />
      <ElTableColumn label="任务／配件需求" min-width="140" align="right"><template #default="{ row }">{{ row.component?.required_quantity ?? row.task_quantity }}</template></ElTableColumn>
      <ElTableColumn label="累积到料/累计出料" min-width="170" align="right">
        <template #default="{ row }">{{ row.component?.received_quantity ?? row.received_quantity }}/{{ row.component ? '—' : row.issued_quantity }}</template>
      </ElTableColumn>
      <ElTableColumn label="操作" min-width="190" :fixed="compact ? false : 'right'"><template #default="{ row }">
        <ElButton v-if="canOperate(row) && row.can_receive" link type="primary" :disabled="row.plan_status !== 'confirmed'" @click="openMovement(row, 'receipt', row.component)">无来源到料</ElButton>
        <ElButton v-if="!row.component && canOperate(row)" link type="primary" :disabled="row.plan_status !== 'confirmed'" @click="openMovement(row, 'issue')">出料</ElButton>
        <ElButton link type="primary" @click="openMovement(row, undefined, row.component)">{{ row.component ? '到料流水' : '流水' }}</ElButton>
      </template></ElTableColumn>
    </ElTable>
    <ElPagination v-if="!error" v-model:current-page="page" class="pagination" layout="prev, pager, next, total" :total="total" :page-size="50" @current-change="load" />
    <DepartmentMovementDialog v-if="movementOrder" :key="`${movementOrder.id}:${movementDirection}:${movementComponent?.material_node_id || ''}`" :order="movementOrder" :direction="movementDirection" :component="movementComponent" @close="movementOrder = null" @changed="movementChanged" />
    <HandoffTicketsPanel v-if="!planId && canReceive" ref="ticketsPanel" :department-code="departmentCode" @changed="load" />
  </section>
</template>

<style scoped>
.pagination { display: flex; justify-content: flex-end; margin-top: 16px; }
.tree-note { color: var(--erp-text-secondary); font-size: 13px; }
</style>
