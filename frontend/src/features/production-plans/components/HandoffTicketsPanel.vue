<script setup lang="ts">
import { type InspectionBatch } from '../api/quality'
import QcInspectionDialog from './QcInspectionDialog.vue'
import QcReworkDialog from './QcReworkDialog.vue'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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
const inspection = ref<InspectionBatch>()
const reworkTicket = ref<HandoffTicket>()
function rowKey(row: HandoffTicket) { return `${row.kind}:${row.id}` }
function readonlyLabel(row: HandoffTicket) {
  if (row.kind === 'rework') return row.action === 'rework_receive' ? '待接收返修' : row.action === 'rework_return' ? '待回交QC' : '已回交QC'
  if (row.kind === 'return') return row.action === 'inspect' ? '待复检' : '已复检'
  return '—'
}
function actionLabel(row: HandoffTicket) {
  return { none: '—', receive: '登记到料', inspect: '质检', rework_receive: '接收返修', rework_return: '回交QC' }[row.action]
}
const canRegisterReceipt = computed(() => Boolean(auth.user?.department_code)
  && auth.hasPermission(DEPARTMENT_WORK_ORDER_OPERATE))
function canReceive(row: HandoffTicket) {
  return canRegisterReceipt.value && row.action !== 'none'
    && row.plan_status === 'confirmed'
}
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
async function handleTicket(row: HandoffTicket) {
  if (opening.value || !canReceive(row)) return
  if (row.action === 'inspect' && row.target_work_order_id !== null) {
    inspection.value = { id: row.id, source_kind: row.kind === 'return' ? 'return' : row.kind === 'warehouse' ? 'warehouse' : 'handoff',
      work_order_id: row.target_work_order_id, order_no: row.order_no,
      product: `${row.factory_code} · ${row.product_name}`, material: `${row.material_no} · ${row.material_name}`, quantity: String(row.quantity) }
  } else if (row.kind === 'rework') reworkTicket.value = row
  else await receive(row)
}
async function receive(row: HandoffTicket) {
  if (opening.value || !canReceive(row) || row.target_work_order_id === null) return
  opening.value = true; error.value = ''
  try {
    const result = await queryDepartmentWorkOrders({ page: 1, work_order_id: row.target_work_order_id })
    if (!active) return
    if (!result.data[0]) throw new Error('目标工单不可访问')
    order.value = result.data[0]; ticket.value = row
  } catch (cause) { if (active) error.value = getApiErrorDetail(cause)?.message || '目标工单不可访问，请刷新后重试' }
  finally { if (active) opening.value = false }
}
function changed() { reworkTicket.value = undefined; inspection.value = undefined; emit('changed'); void load() }
defineExpose({ refresh: load })
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>
<template>
  <section class="ticket-panel">
    <div class="collection-heading">
      <div><h2>物料交接</h2></div>
    </div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" :row-key="rowKey" empty-text="暂无符合条件的交接票">
      <ElTableColumn prop="source_department" label="来自" min-width="100" />
      <ElTableColumn class-name="data-primary" label="产品" min-width="180">
        <template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template>
      </ElTableColumn>
      <ElTableColumn class-name="data-primary" label="配件/装配体" min-width="240">
        <template #default="{ row }">{{ row.material_no }} · {{ row.material_name }}</template>
      </ElTableColumn>
      <ElTableColumn class-name="data-reference" prop="order_no" label="订单号" min-width="150" />
      <ElTableColumn class-name="data-metric" prop="quantity" label="数量" width="120" align="right" />
      <ElTableColumn class-name="data-secondary" prop="created_at" label="时间" min-width="180" />
      <ElTableColumn label="操作" width="110">
        <template #default="{ row }">
          <ElButton v-if="canRegisterReceipt && row.action !== 'none'" link type="primary" :disabled="loading || opening || !canReceive(row)" @click="handleTicket(row)">{{ actionLabel(row) }}</ElButton>
          <span v-else>{{ readonlyLabel(row) }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn class-name="data-secondary" prop="note" label="备注" min-width="140" />
    </ElTable>
    <ElPagination v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
    <QcReworkDialog v-if="reworkTicket" :key="`${reworkTicket.id}:${reworkTicket.action}`" :ticket="reworkTicket" @close="reworkTicket = undefined" @saved="changed" />
    <QcInspectionDialog v-if="inspection" :key="`${inspection.source_kind}:${inspection.id}`" :batch="inspection" @close="inspection = undefined" @saved="changed" />
    <DepartmentMovementDialog v-if="ticket && order" :order="order" direction="receipt" :ticket="ticket" @close="ticket = undefined; order = undefined" @changed="changed" />
  </section>
</template>
<style scoped>
.ticket-panel { min-width: 0; padding: 24px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
p { color: var(--erp-text-secondary); font-size: 14px; }
.el-pagination { margin-top: 14px; }
@media (max-width: 760px) { .ticket-panel { padding: 16px; } }
</style>
