<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { ElMessage } from 'element-plus'
import {
  queryDepartmentMovements, recordDepartmentMovement,
  queryHandoffOptions, type HandoffOptions, type HandoffTicket,
  type DepartmentMovement, type DepartmentMovementInput, type DepartmentWorkOrder, type WorkOrderComponent,
} from '../api/plans'

const props = defineProps<{ order: DepartmentWorkOrder; direction?: 'receipt' | 'issue'; ticket?: HandoffTicket; component?: WorkOrderComponent }>()
const emit = defineEmits<{ close: []; changed: [] }>()
const visible = ref(true)
const quantity = ref<number>()
const note = ref('')
const saving = ref(false)
const saveError = ref('')
const rows = ref<DepartmentMovement[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const title = computed(() => props.direction === 'receipt' ? '到料登记' : props.direction === 'issue' ? '出料登记' : props.component ? '配件到料流水' : '到料／出料流水')
let active = true
let revision = 0
let pending: DepartmentMovementInput | undefined
const options = ref<HandoffOptions>()
const optionError = ref('')
const optionLoading = ref(false)
const target = ref<number>()
const input = ref(props.component?.material_node_id || '')
const excessIssue = computed(() => props.direction === 'issue'
  && options.value?.available_issue_quantity != null
  && quantity.value !== undefined && Number.isSafeInteger(quantity.value) && quantity.value > 0
  && BigInt(quantity.value) > BigInt(options.value.available_issue_quantity))
const noteRequired = computed(() => excessIssue.value || (props.direction === 'receipt'
  && (!props.ticket || (quantity.value !== undefined && quantity.value < props.ticket.quantity))))
const quantityMax = computed(() => {
  let available: bigint | undefined
  if (props.direction === 'receipt' && props.ticket) available = BigInt(props.ticket.quantity) - BigInt(props.ticket.received_quantity)
  if (available === undefined) return Number.MAX_SAFE_INTEGER
  return Number(available < 0n ? 0n : available > BigInt(Number.MAX_SAFE_INTEGER) ? BigInt(Number.MAX_SAFE_INTEGER) : available)
})
const ticketRemaining = computed(() => props.ticket
  ? (BigInt(props.ticket.quantity) - BigInt(props.ticket.received_quantity)).toString()
  : '')
async function loadOptions() {
  optionLoading.value = true; optionError.value = ''
  try {
    const result = await queryHandoffOptions(props.order.id)
    if (!active) return
    if (props.component && !result.external_inputs.some(item => item.material_node_id === props.component!.material_node_id)) {
      optionError.value = '此配件已不属于当前工单，请关闭后刷新工单'
      return
    }
    options.value = result
    if (result.targets.length === 1) target.value = result.targets[0]!.id
    if (!props.component && result.external_inputs.length === 1) input.value = result.external_inputs[0]!.material_node_id
  } catch (cause) {
    if (active) optionError.value = getApiErrorDetail(cause)?.message || '来料及去向加载失败'
  } finally { if (active) optionLoading.value = false }
}

async function load() {
  const current = ++revision
  loading.value = true
  error.value = ''
  rows.value = []
  try {
    const result = await queryDepartmentMovements(props.order.id, page.value, props.component?.material_node_id)
    if (!active || current !== revision) return
    rows.value = result.data
    total.value = result.total
  } catch (cause) {
    if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '流水加载失败'
  } finally { if (active && current === revision) loading.value = false }
}

async function save() {
  if (saving.value || !props.direction) return
  if (!options.value || optionLoading.value || optionError.value) return
  if (props.direction === 'receipt' && !options.value.can_receive) { saveError.value = '本部门无需登记到料，请直接出料'; return }
  if (!Number.isSafeInteger(quantity.value) || !quantity.value || quantity.value <= 0) {
    saveError.value = '请输入正整数数量'
    return
  }
  if (quantity.value > quantityMax.value) { saveError.value = `本票剩余可到料 ${quantityMax.value}`; return }
  if (noteRequired.value && !note.value.trim()) {
    saveError.value = excessIssue.value ? '本次出料超过部门停留数量，必须填写备注'
      : props.ticket ? '登记到料数量小于交接票数量，必须填写备注' : '无来源到料必须填写备注'
    return
  }
  if (props.direction === 'issue' && options.value.targets.length && !target.value) { saveError.value = '请选择出料去向'; return }
  if (props.direction === 'receipt' && !props.ticket && !input.value) { saveError.value = '请选择实际到料物料'; return }
  const value: Omit<DepartmentMovementInput, 'request_id'> = {
    direction: props.direction, quantity: quantity.value, note: note.value.trim(),
    receipt_source: props.direction === 'receipt' ? (props.ticket ? 'ticket' : 'external') : null,
    ticket_id: props.direction === 'receipt' && props.ticket ? props.ticket.id : null,
    input_material_node_id: props.direction === 'receipt' && !props.ticket ? input.value : null,
    target_work_order_id: props.direction === 'issue' ? target.value ?? null : null,
  }
  if (!pending || JSON.stringify({ ...pending, request_id: undefined }) !== JSON.stringify(value)) {
    pending = { ...value, request_id: crypto.randomUUID() }
  }
  saving.value = true
  saveError.value = ''
  try {
    const result = await recordDepartmentMovement(props.order.id, pending)
    if (!active) return
    ElMessage.success(result.ticket_no ? `已保存，交接票 ${result.ticket_no}` : '登记已保存')
    emit('changed')
    visible.value = false
  } catch (cause) {
    if (active) saveError.value = getApiErrorDetail(cause)?.message || '登记失败，请重试；相同内容重试不会重复记账'
  } finally { if (active) saving.value = false }
}

function beforeClose(done: () => void) { if (!saving.value) done() }
onMounted(() => { if (props.direction) void loadOptions(); else void load() })
onBeforeUnmount(() => { active = false; revision += 1 })
</script>

<template>
  <ElDialog v-model="visible" :title="title" width="min(1000px, 96vw)" :before-close="beforeClose" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @closed="emit('close')">
    <p>{{ order.order_no }} · {{ order.department_name }} · {{ order.part_name }}</p>
    <p v-if="component">配件：{{ component.part_no }} · {{ component.part_name }}（仅此配件直接到料）</p>
    <ElForm v-if="direction" label-width="80px" @submit.prevent="save">
      <LoadErrorAlert :message="optionError" :loading="optionLoading" @retry="loadOptions" />
      <template v-if="direction === 'receipt'">
        <section v-if="ticket" class="ticket-summary" aria-label="交接票数量核对">
          <p>{{ ticket.ticket_no }} · {{ ticket.factory_code }} {{ ticket.product_name }} · {{ ticket.material_name }}</p>
          <p>{{ ticket.source_department }} → {{ ticket.target_department }}</p>
          <div class="ticket-quantity"><span>交接票数量</span><strong>{{ ticket.quantity }}</strong></div>
          <div class="ticket-balance"><span>已到料：{{ ticket.received_quantity }}</span><span>剩余可到料：<b>{{ ticketRemaining }}</b></span></div>
        </section>
        <template v-else>
          <p>本次为无来源到料，请确认工单与实际物料，并在备注中说明原因。</p>
          <ElFormItem label="实际物料"><ElSelect v-model="input" :disabled="saving || optionLoading || !!component" placeholder="请选择实际到料物料"><ElOption v-for="part in options?.external_inputs" :key="part.material_node_id" :label="part.label" :value="part.material_node_id" /></ElSelect></ElFormItem>
        </template>
      </template>
      <template v-else>
        <p v-if="options">{{ options.available_issue_quantity === null ? '本部门直接出料，不受到料数量限制。' : `部门停留数量：${options.available_issue_quantity}（装配体按 BOM 齐套折算）；超过此数量出料必须填写备注。` }} <ElButton text :loading="optionLoading" :disabled="saving" @click="loadOptions">刷新停留量</ElButton></p>
        <ElFormItem v-if="options?.targets.length" label="去向"><ElSelect v-model="target" :disabled="saving || optionLoading" style="width:100%"><ElOption v-for="item in options.targets" :key="item.id" :label="item.label" :value="item.id" /></ElSelect></ElFormItem>
        <p v-else-if="options">终端出料：不生成内部交接票。</p>
      </template>
      <ElFormItem label="数量"><ElInputNumber v-model="quantity" :min="1" :max="Math.max(1, quantityMax)" :precision="0" :step="1" :disabled="saving || quantityMax <= 0" controls-position="right" /></ElFormItem>
      <ElFormItem label="备注" :required="noteRequired"><ElInput v-model="note" type="textarea" :rows="2" maxlength="1000" show-word-limit :disabled="saving" /></ElFormItem>
      <p class="movement-note">累计交接到料不能超出票面数量；本次到料小于票面数量、无来源到料、或出料超过部门停留数量时备注必填。流水保存后不可修改或删除。</p>
      <LoadErrorAlert :message="saveError" title="登记未完成" retry-text="重试保存" :loading="saving" @retry="save" />
      <ElFormItem><ElButton type="primary" native-type="submit" :disabled="optionLoading || !!optionError || !options || quantityMax <= 0" :loading="saving">保存{{ direction === 'receipt' ? '到料' : '出料' }}</ElButton></ElFormItem>
    </ElForm>
    <template v-if="!direction">
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" border empty-text="暂无到料或出料流水">
      <ElTableColumn label="类型" width="90"><template #default="{ row }">{{ row.direction === 'receipt' ? '到料' : '出料' }}</template></ElTableColumn>
      <ElTableColumn label="来自/到达" min-width="140"><template #default="{ row }">{{ row.direction === 'receipt' ? (row.source_department || '无来源到料') : (row.target_department || '终端出料') }}</template></ElTableColumn>
      <ElTableColumn prop="material_name" label="实际物料" min-width="150" />
      <ElTableColumn prop="quantity" label="数量" width="140" align="right" />
      <ElTableColumn prop="actor_username" label="操作人" min-width="110" />
      <ElTableColumn prop="created_at" label="时间" min-width="210" />
      <ElTableColumn prop="note" label="备注" min-width="180" />
    </ElTable>
    <ElPagination v-if="!error" v-model:current-page="page" layout="prev, pager, next, total" :total="total" :page-size="50" @current-change="load" />
    </template>
    <template #footer><ElButton :disabled="saving" @click="visible = false">关闭</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.movement-note { color: var(--erp-text-secondary); font-size: 13px; line-height: 1.6; }
.el-pagination { margin-top: 16px; justify-content: flex-end; }
.ticket-summary { margin: 12px 0 20px; padding: 16px; border: 2px solid var(--erp-primary); border-radius: 8px; background: var(--erp-primary-soft); }
.ticket-summary p { margin: 0 0 6px; overflow-wrap: anywhere; }
.ticket-quantity { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 16px; margin: 12px 0; color: var(--erp-primary-strong); }
.ticket-quantity strong { font-size: 36px; font-weight: 750; line-height: 1.3; overflow-wrap: anywhere; }
.ticket-balance { display: flex; flex-wrap: wrap; gap: 8px 24px; font-variant-numeric: tabular-nums; }
</style>
