<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { DEPARTMENT_WORK_ORDER_OPERATE } from '@/permission/constants'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import DepartmentMovementDialog from './DepartmentMovementDialog.vue'
import { queryHandoffTickets, queryDepartmentWorkOrders, type HandoffTicket, type DepartmentWorkOrder } from '../api/plans'
const props = defineProps<{ departmentCode?: string }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const rows = ref<HandoffTicket[]>([]), total = ref(0), page = ref(1)
const unreceived = ref(true), keyword = ref(''), loading = ref(false), error = ref('')
const ticket = ref<HandoffTicket>(), order = ref<DepartmentWorkOrder>()
const opening = ref(false)
function remaining(row: HandoffTicket) { return (BigInt(row.quantity) - BigInt(row.received_quantity)).toString() }
let active = true, revision = 0
async function load() {
  const current = ++revision; loading.value = true; error.value = ''; rows.value = []
  try {
    const result = await queryHandoffTickets({ page: page.value, unreceived: unreceived.value, order_no: keyword.value.trim() || undefined, department_code: props.departmentCode })
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value-1)*50) { page.value = Math.max(1,Math.ceil(result.total/50)); await load(); return }
    rows.value = result.data; total.value = result.total
  } catch (cause) { if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '交接票加载失败' }
  finally { if (active && current === revision) loading.value = false }
}
function search() { page.value = 1; void load() }
async function receive(row: HandoffTicket) {
  if (opening.value) return
  opening.value = true; error.value = ''
  try {
    const result = await queryDepartmentWorkOrders({ page: 1, work_order_id: row.target_work_order_id })
    if (!active) return
    if (!result.data[0]) throw new Error('目标工单不可访问')
    order.value = result.data[0]; ticket.value = row
  } catch (cause) { if (active) error.value = getApiErrorDetail(cause)?.message || '目标工单不可访问，请刷新后重试' }
  finally { if (active) opening.value = false }
}
function changed() { emit('changed'); void load() }
defineExpose({ refresh: load })
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
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
