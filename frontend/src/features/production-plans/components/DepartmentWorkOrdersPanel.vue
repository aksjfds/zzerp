<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useCompactViewport } from '@/shared/layout/useCompactViewport'
import { usePagedQuery } from '@/shared/query/usePagedQuery'
import { useRequest } from '@/shared/query/useRequest'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { useAuthStore, DEPARTMENT_WORK_ORDER_OPERATE } from '@/features/identity'
import { queryProductionDepartments, type ProductionDepartment } from '@/features/production-departments'
import DepartmentMovementDialog from './DepartmentMovementDialog.vue'
import HandoffTicketsPanel from './HandoffTicketsPanel.vue'
import { queryDepartmentWorkOrders } from '../api/plans'
import type { DepartmentWorkOrder, WorkOrderComponent } from '../domain/types'

const compact = useCompactViewport()
const props = defineProps<{ planId?: number; departmentCode?: string; canReceive?: boolean }>()
const authStore = useAuthStore()
const movementOrder = ref<DepartmentWorkOrder | null>(null)
const movementDirection = ref<'receipt' | 'issue'>()
const movementComponent = ref<WorkOrderComponent>()
const ticketsPanel = ref<InstanceType<typeof HandoffTicketsPanel>>()
const filters = reactive({ department_code: '', order_no: '', product_keyword: '' })
const { data: rows, total, page, loading, error, load, search } = usePagedQuery<DepartmentWorkOrder>(
  ({ page, signal }) => queryDepartmentWorkOrders({
    page, department_code: props.departmentCode || filters.department_code || undefined,
    plan_id: props.planId, order_no: filters.order_no.trim() || undefined,
    product_keyword: filters.product_keyword.trim() || undefined,
  }, signal),
  '部门生产安排加载失败',
)
const departmentRequest = useRequest<ProductionDepartment[]>('生产部门加载失败')
const departments = computed(() => departmentRequest.data.value ?? [])
const departmentError = departmentRequest.error
const departmentLoading = departmentRequest.loading
function loadDepartments() { return departmentRequest.run(queryProductionDepartments) }
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
type WorkOrderRow = DepartmentWorkOrder & {
  row_key: string; component?: WorkOrderComponent; children?: WorkOrderRow[]
}
const tableRows = computed<WorkOrderRow[]>(() => rows.value.map(order => ({
  ...order, row_key: `order:${order.id}`,
  children: order.components.length ? order.components.map(component => ({
    ...order, row_key: `order:${order.id}:part:${component.material_node_id}`, component,
  })) : undefined,
})))
const hasComponents = computed(() => rows.value.some(order => order.components.length > 0))
function clear() {
  Object.assign(filters, { department_code: '', order_no: '', product_keyword: '' })
  void search()
}
onMounted(() => { if (!props.departmentCode) void loadDepartments() })
watch(() => [props.departmentCode, props.planId], () => { void search() })
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
      <ElTableColumn prop="appearance_name" label="外观" min-width="120" />
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
