<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAuthStore, DEPARTMENT_WORK_ORDER_OPERATE } from '@/features/identity'
import { usePagedQuery } from '@/shared/query/usePagedQuery'
import { useRequest } from '@/shared/query/useRequest'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import DepartmentMovementDialog from './DepartmentMovementDialog.vue'
import { queryHandoffTickets, queryDepartmentWorkOrders } from '../api/plans'
import type { HandoffTicket, DepartmentWorkOrder } from '../domain/types'

const props = defineProps<{ departmentCode?: string }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const unreceived = ref(true), keyword = ref('')
const ticket = ref<HandoffTicket>(), order = ref<DepartmentWorkOrder>()
const openingRequest = useRequest<DepartmentWorkOrder>('目标工单不可访问，请刷新后重试')
const opening = openingRequest.loading
const {
  data: rows, total, page, loading, error: listError, load: reload, search: searchTickets,
} = usePagedQuery<HandoffTicket>(
  ({ page, signal }) => queryHandoffTickets({
    page, unreceived: unreceived.value, order_no: keyword.value.trim() || undefined,
    department_code: props.departmentCode,
  }, signal),
  '交接票加载失败',
)
const error = computed(() => openingRequest.error.value || listError.value)
function remaining(row: HandoffTicket) {
  return (BigInt(row.quantity) - BigInt(row.received_quantity)).toString()
}
function load() { openingRequest.error.value = ''; return reload() }
function search() { openingRequest.error.value = ''; return searchTickets() }

async function receive(row: HandoffTicket) {
  if (opening.value) return
  const target = await openingRequest.run(async signal => {
    const result = await queryDepartmentWorkOrders({
      page: 1, work_order_id: row.target_work_order_id,
    }, signal)
    if (!result.data[0]) throw new Error('目标工单不可访问')
    return result.data[0]
  })
  if (target) { order.value = target; ticket.value = row }
}
function changed() { emit('changed'); void load() }
defineExpose({ refresh: load })
</script>
<template>
  <section class="ticket-panel">
    <h3>交接票到料</h3>
    <ElForm inline @submit.prevent="search">
      <ElFormItem label="订单号"><ElInput v-model="keyword" clearable maxlength="200" /></ElFormItem>
      <ElFormItem><ElCheckbox v-model="unreceived" @change="search">仅未登记到料</ElCheckbox></ElFormItem>
      <ElFormItem><ElButton native-type="submit" :loading="loading">查询/刷新</ElButton></ElFormItem>
    </ElForm>
    <p>接收过的票可继续分批到料，取消“仅未登记到料”即可查看；累计到料不得超过对应出料数。</p>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" border empty-text="暂无符合条件的交接票">
      <ElTableColumn prop="ticket_no" label="交接票" min-width="140" />
      <ElTableColumn prop="appearance_name" label="外观" min-width="120" />
      <ElTableColumn prop="order_no" label="订单号" min-width="150" />
      <ElTableColumn label="产品" min-width="180"><template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template></ElTableColumn>
      <ElTableColumn prop="material_name" label="实际来料" min-width="160" />
      <ElTableColumn prop="source_department" label="来自" min-width="100" />
      <ElTableColumn prop="target_department" label="到达" min-width="100" />
      <ElTableColumn prop="quantity" label="上游出料" width="120" />
      <ElTableColumn prop="received_quantity" label="已登记到料" min-width="130" />
      <ElTableColumn label="剩余可到料" min-width="130"><template #default="{ row }">{{ remaining(row) }}</template></ElTableColumn>
      <ElTableColumn prop="created_at" label="出料时间" min-width="180" />
      <ElTableColumn prop="note" label="备注" min-width="140" />
      <ElTableColumn v-if="auth.user?.department_code && auth.hasPermission(DEPARTMENT_WORK_ORDER_OPERATE)" label="操作" width="100"><template #default="{ row }"><ElButton v-if="row.can_receive" link type="primary" :disabled="row.plan_status !== 'confirmed' || opening || remaining(row) === '0'" @click="receive(row)">登记到料</ElButton></template></ElTableColumn>
    </ElTable>
    <ElPagination v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
    <DepartmentMovementDialog v-if="ticket && order" :order="order" direction="receipt" :ticket="ticket" @close="ticket = undefined; order = undefined" @changed="changed" />
  </section>
</template>
<style scoped>
.ticket-panel { margin-top: 24px; }
p { color: var(--erp-text-secondary); font-size: 13px; }
.el-pagination { margin-top: 14px; }
</style>
