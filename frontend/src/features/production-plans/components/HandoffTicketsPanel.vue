<script setup lang="ts">
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
const canRegisterReceipt = computed(() => Boolean(auth.user?.department_code)
  && auth.hasPermission(DEPARTMENT_WORK_ORDER_OPERATE))
function canReceive(row: HandoffTicket) {
  return canRegisterReceipt.value && row.can_receive && BigInt(row.received_quantity) === 0n
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
async function receive(row: HandoffTicket) {
  if (opening.value || !canReceive(row)) return
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
    <div class="collection-heading">
      <div><h2>物料交接</h2></div>
    </div>


    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" row-key="id" empty-text="暂无符合条件的交接票">
      <ElTableColumn prop="source_department" label="来自" min-width="100" />
      <ElTableColumn label="产品" min-width="180">
        <template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template>
      </ElTableColumn>
      <ElTableColumn label="配件/装配体" min-width="240">
        <template #default="{ row }">{{ row.material_no }} · {{ row.material_name }}</template>
      </ElTableColumn>
      <ElTableColumn prop="order_no" label="订单号" min-width="150" />
      <ElTableColumn prop="quantity" label="数量" width="120" align="right" />
      <ElTableColumn prop="created_at" label="时间" min-width="180" />
      <ElTableColumn label="操作" width="110">
        <template #default="{ row }">
          <ElButton v-if="canRegisterReceipt && row.can_receive && BigInt(row.received_quantity) === 0n" link type="primary" :disabled="loading || opening || !canReceive(row)" @click="receive(row)">登记到料</ElButton>
          <span v-else>—</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="note" label="备注" min-width="140" />
    </ElTable>
    <ElPagination v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
    <DepartmentMovementDialog v-if="ticket && order" :order="order" direction="receipt" :ticket="ticket" @close="ticket = undefined; order = undefined" @changed="changed" />
  </section>
</template>
<style scoped>
.ticket-panel { min-width: 0; padding: 24px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
p { color: var(--erp-text-secondary); font-size: 14px; }
.el-pagination { margin-top: 14px; }
@media (max-width: 760px) { .ticket-panel { padding: 16px; } }
</style>
