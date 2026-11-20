<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { ElMessage } from 'element-plus'
import ProductionDocumentPrintDialog from './ProductionDocumentPrintDialog.vue'
import ProductionDocumentSheet from './ProductionDocumentSheet.vue'
import { printElement } from '@/shared/printing/printElement'
import {
  queryDepartmentMovements, recordDepartmentMovement,
  queryHandoffOptions, type HandoffOptions, type HandoffTicket,
  type DepartmentMovement, type DepartmentLedgerMovement, type DepartmentMovementInput, type DepartmentWorkOrder, type WorkOrderComponent,
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
const title = computed(() => props.direction === 'receipt' ? '到料登记' : props.direction === 'issue' ? '物料交接单' : props.component ? '配件到料流水' : '到料／出料流水')
let active = true
let revision = 0
let pending: DepartmentMovementInput | undefined
const options = ref<HandoffOptions>()
const optionError = ref('')
const optionLoading = ref(false)
const target = ref<number>()
const documentType = ref<'normal' | 'piecework'>('normal'), workerName = ref('')
const pieceworkProcess = ref('')
const canPiecework = computed(() => props.direction === 'issue' && !!options.value?.targets.find(item => item.id === target.value)?.can_piecework)
const documentTitle = computed(() => documentType.value === 'piecework' ? '物料交接单 - 计件单' : '物料交接单 - 普通交接')
watch(canPiecework, allowed => { if (!allowed) documentType.value = 'normal' })
watch(documentType, value => { if (value === 'normal') { workerName.value = ''; pieceworkProcess.value = '' } })
const printMovement = ref<DepartmentLedgerMovement>()
const saved = ref(false)
const draftSheet = ref<InstanceType<typeof ProductionDocumentSheet>>()
const printing = ref(false)
const issueFields = computed<[string, string | null, string?][]>(() => [
  ...(canPiecework.value ? [['单据', null, 'document'] as [string, string | null, string?]] : []),
  ...(documentType.value === 'piecework' ? [['工艺', null, 'pieceworkProcess'] as [string, string | null, string?]] : []),
  ['产品', `${props.order.factory_code} · ${props.order.product_name}`],
  ['配件/装配体', `${props.order.part_no} · ${props.order.part_name}`],
  ['交接', null, 'handoff'], ['备注', null, 'note'],
])
const draftFields = computed<[string, string | null][]>(() => [
  ...(documentType.value === 'piecework' ? [['磨房工人', workerName.value.trim()] as [string, string | null]] : []),
  ...(documentType.value === 'piecework' ? [['工艺', pieceworkProcess.value.trim()] as [string, string | null]] : []),
  ['产品', `${props.order.factory_code} · ${props.order.product_name}`],
  ['配件/装配体', `${props.order.part_no} · ${props.order.part_name}`],
  ['交接', `${props.order.department_name} -> ${options.value?.targets.find(item => item.id === target.value)?.department_name || '终端出料'}，${quantity.value ?? ''}`],
  ['备注', note.value.trim()],
])
async function printDraft() {
  if (printing.value || saving.value || !draftSheet.value?.element) return
  if (!Number.isSafeInteger(quantity.value) || !quantity.value || quantity.value < 1
    || (options.value?.targets.length && !target.value)) {
    saveError.value = '请选择交接去向并输入正整数数量'; return
  }
  printing.value = true
  if (documentType.value === 'piecework' && !workerName.value.trim()) { printing.value = false; saveError.value = '请填写磨房工人姓名'; return }
  try { await printElement(draftSheet.value.element, documentTitle.value) }
  catch (cause) { if (active) ElMessage.error(cause instanceof Error ? cause.message : '打印失败，请重试') }
  finally { if (active) printing.value = false }
}
function openPrint(movement: DepartmentMovement) {
  if (movement.direction !== 'issue' || !movement.ticket_no) return
  printMovement.value = { ...movement, order_no: props.order.order_no, factory_code: props.order.factory_code,
    product_name: props.order.product_name, department_name: props.order.department_name }
}
function closePrint() { printMovement.value = undefined; if (props.direction) visible.value = false }
const noteRequired = computed(() => props.direction === 'receipt' && props.ticket !== undefined
  && quantity.value !== undefined && quantity.value < props.ticket.quantity)
const quantityMax = computed(() => {
  let available: bigint | undefined
  if (props.direction === 'receipt' && props.ticket) available = BigInt(props.ticket.quantity)
  if (props.direction === 'issue' && options.value) {
    if (options.value.available_issue_quantity === null) return Number.MAX_SAFE_INTEGER
    available = BigInt(options.value.available_issue_quantity)
  }
  if (available === undefined) return 0
  return Number(available < 0n ? 0n : available > BigInt(Number.MAX_SAFE_INTEGER) ? BigInt(Number.MAX_SAFE_INTEGER) : available)
})
async function loadOptions() {
  optionLoading.value = true; optionError.value = ''
  try {
    const result = await queryHandoffOptions(props.order.id)
    if (!active) return
    options.value = result
    if (result.targets.length === 1) target.value = result.targets[0]!.id
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
  if (saving.value || printing.value || saved.value || !props.direction) return
  if (!options.value || optionLoading.value || optionError.value) return
  if (props.direction === 'receipt' && (!props.ticket || !props.ticket.can_receive)) { saveError.value = '到料必须通过发给本部门的可接收交接票登记'; return }
  if (!Number.isSafeInteger(quantity.value) || !quantity.value || quantity.value <= 0) {
    saveError.value = '请输入正整数数量'
    return
  }
  if (props.direction === 'receipt' && props.ticket && BigInt(props.ticket.received_quantity) > 0n) {
    saveError.value = '此交接票已登记到料，不能再次登记'
    return
  }
  if (quantity.value > quantityMax.value) {
    saveError.value = props.direction === 'issue' ? `出料数量不能超过可出料数量 ${quantityMax.value}` : `到料数量不能超过票面数量 ${quantityMax.value}`
    return
  }
  if (noteRequired.value && !note.value.trim()) {
    saveError.value = '登记到料数量小于交接票数量，必须填写备注'
    return
  }
  if (props.direction === 'issue' && options.value.targets.length && !target.value) { saveError.value = '请选择出料去向'; return }
  if (documentType.value === 'piecework' && !workerName.value.trim()) { saveError.value = '请填写磨房工人姓名'; return }
  const value: Omit<DepartmentMovementInput, 'request_id'> = {
    document_type: documentType.value, worker_name: workerName.value.trim(),
    piecework_process: documentType.value === 'piecework' ? pieceworkProcess.value.trim() : '',
    direction: props.direction, quantity: quantity.value, note: note.value.trim(),
    receipt_source: props.direction === 'receipt' ? (props.ticket?.kind === 'warehouse' ? 'warehouse' : 'ticket') : null,
    ticket_id: props.direction === 'receipt' && props.ticket?.kind !== 'warehouse' ? props.ticket?.id ?? null : null,
    warehouse_pick_id: props.direction === 'receipt' && props.ticket?.kind === 'warehouse' ? props.ticket.id : null,
    input_material_node_id: null,
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
    saved.value = true
    ElMessage.success(result.ticket_no ? `已保存，交接票 ${result.ticket_no}` : '登记已保存')
    emit('changed')
    visible.value = false
  } catch (cause) {
    if (active) saveError.value = getApiErrorDetail(cause)?.message || '登记失败，请重试；相同内容重试不会重复记账'
  } finally { if (active) saving.value = false }
}

function beforeClose(done: () => void) { if (!saving.value && !printing.value) done() }
onMounted(() => { if (props.direction) void loadOptions(); else void load() })
onBeforeUnmount(() => { active = false; revision += 1 })
</script>

<template>
  <ElDialog v-model="visible" :title="title" :width="direction === 'issue' ? 'min(760px, 96vw)' : direction ? 'min(520px, 94vw)' : 'min(1000px, 96vw)'" :before-close="beforeClose" :close-on-click-modal="!saving && !printing" :close-on-press-escape="!saving && !printing" :show-close="!saving && !printing" @closed="emit('close')">
<div v-if="direction !== 'issue'" class="movement-context"><span>当前工单</span><h3>{{ order.part_name }}</h3><p><strong>{{ order.order_no }}</strong><span>{{ order.department_name }}</span></p></div>
    <p v-if="component">配件：{{ component.part_no }} · {{ component.part_name }}</p>
    <template v-if="direction === 'issue'">
      <ElForm :disabled="saving || printing" @submit.prevent="save()">
        <LoadErrorAlert :message="optionError" :loading="optionLoading" @retry="loadOptions" />
        <ProductionDocumentSheet :title="documentTitle" :fields="issueFields">
          <template #document><ElRadioGroup v-model="documentType"><ElRadioButton value="normal">普通单</ElRadioButton><ElRadioButton value="piecework">计件单</ElRadioButton></ElRadioGroup><ElInput v-if="documentType === 'piecework'" v-model="workerName" aria-label="磨房工人姓名" maxlength="100" placeholder="磨房工人姓名" /></template>
          <template #pieceworkProcess><ElInput v-model="pieceworkProcess" aria-label="工艺" maxlength="100" /></template>
          <template #handoff>
            <div class="handoff-inputs"><span>{{ order.department_name }} -&gt;</span>
              <ElSelect v-if="options?.targets.length" v-model="target" aria-label="接收部门" :disabled="optionLoading" placeholder="选择接收部门"><ElOption v-for="item in options.targets" :key="item.id" :label="item.label" :value="item.id" /></ElSelect>
              <span v-else>{{ optionLoading || !options ? '加载中' : '终端出料' }}</span><span>，</span>
              <ElInputNumber v-model="quantity" aria-label="交接数量" :min="1" :max="Math.max(1, quantityMax)" :precision="0" :disabled="quantityMax <= 0" controls-position="right" />
            </div>
          </template>
          <template #note><ElInput v-model="note" aria-label="备注" type="textarea" :rows="3" maxlength="1000" show-word-limit /></template>
        </ProductionDocumentSheet>
        <p v-if="options">可出料数量：{{ options.available_issue_quantity === null ? '不限' : quantityMax }} <ElButton text :loading="optionLoading" :disabled="saving" @click="loadOptions">刷新数量</ElButton></p>
        <LoadErrorAlert :message="saveError" title="登记未完成" retry-text="重试" :loading="saving" @retry="save()" />
      </ElForm>
      <div hidden><ProductionDocumentSheet ref="draftSheet" :title="documentTitle" :fields="draftFields" /></div>
    </template>
    <ElForm v-else-if="direction === 'receipt'" label-position="top" :disabled="saved" @submit.prevent="save()">
      <LoadErrorAlert :message="optionError" :loading="optionLoading" @retry="loadOptions" />
      <template v-if="direction === 'receipt'">
        <section v-if="ticket" class="ticket-summary" aria-label="交接票数量核对">
          <p>{{ ticket.ticket_no }} · {{ ticket.factory_code }} {{ ticket.product_name }} · {{ ticket.material_name }}</p>
          <p>{{ ticket.source_department }} → {{ ticket.target_department }}</p>
          <div class="ticket-quantity"><span>交接票数量</span><strong>{{ ticket.quantity }}</strong></div>
          <div class="ticket-balance"><span>已到料：{{ ticket.received_quantity }}</span></div>
        </section>
      </template>
      <ElFormItem label="数量"><ElInputNumber v-model="quantity" :min="1" :max="Math.max(1, quantityMax)" :precision="0" :step="1" :disabled="saving || quantityMax <= 0" controls-position="right" /></ElFormItem>
      <ElFormItem label="备注" :required="noteRequired"><ElInput v-model="note" type="textarea" :rows="2" maxlength="1000" show-word-limit :disabled="saving" /></ElFormItem>
      <LoadErrorAlert :message="saveError" title="登记未完成" retry-text="重试保存" :loading="saving" @retry="save()" />
      <ElFormItem><ElButton type="primary" native-type="submit" :disabled="optionLoading || !!optionError || !options || quantityMax <= 0" :loading="saving">保存到料</ElButton></ElFormItem>
    </ElForm>
    <template v-if="!direction">
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" empty-text="暂无到料或出料流水">
      <ElTableColumn label="类型" width="90"><template #default="{ row }">{{ row.direction === 'receipt' ? '到料' : '出料' }}</template></ElTableColumn>
      <ElTableColumn label="来自/到达" min-width="140"><template #default="{ row }">{{ row.direction === 'receipt' ? (row.source_department || '无来源到料') : (row.target_department || '终端出料') }}</template></ElTableColumn>
      <ElTableColumn prop="material_name" label="实际物料" min-width="150" />
      <ElTableColumn prop="quantity" label="数量" width="140" align="right" />
      <ElTableColumn prop="actor_username" label="操作人" min-width="110" />
      <ElTableColumn prop="created_at" label="时间" min-width="210" />
      <ElTableColumn prop="note" label="备注" min-width="180" />
      <ElTableColumn label="操作" width="90"><template #default="{ row }"><ElButton v-if="row.direction === 'issue' && row.ticket_no" link type="primary" @click="openPrint(row)">打印</ElButton></template></ElTableColumn>
    </ElTable>
    <ElPagination v-if="!error" v-model:current-page="page" layout="prev, pager, next, total" :total="total" :page-size="50" @current-change="load" />
    </template>
    <template #footer><ElButton :disabled="saving || printing" @click="visible = false">关闭</ElButton><template v-if="direction === 'issue'"><ElButton :disabled="printing || optionLoading || !!optionError || !options || quantityMax <= 0" :loading="saving" @click="save()">出料</ElButton><ElButton type="primary" :disabled="saving || optionLoading || !!optionError || !options" :loading="printing" @click="printDraft">打印</ElButton></template></template>
  </ElDialog>
  <ProductionDocumentPrintDialog v-if="printMovement && direction !== 'issue'" :document="{ kind: 'issue', record: printMovement }" @close="closePrint" />
</template>

<style scoped>

.el-pagination { margin-top: 16px; justify-content: flex-end; }
.handoff-inputs { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.handoff-inputs .el-select { flex: 1 1 150px; min-width: 130px; }
.ticket-summary { margin: 16px 0 24px; padding: 24px; border: 1px solid var(--el-color-primary-light-8); border-radius: 12px; background: var(--erp-primary-soft); }
.ticket-summary p { margin: 0 0 6px; overflow-wrap: anywhere; }
.ticket-quantity { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 16px; margin: 12px 0; color: var(--erp-primary-strong); }
.ticket-quantity strong { font-size: 36px; font-weight: 700; line-height: 1.3; overflow-wrap: anywhere; }
.ticket-balance { display: flex; flex-wrap: wrap; gap: 8px 24px; font-variant-numeric: tabular-nums; }
.movement-context { padding: 20px; margin-bottom: 24px; border: 1px solid var(--erp-border); border-radius: 8px; background: var(--erp-surface-muted); }.movement-context > span { font-size: 11px; color: var(--erp-text-muted); }.movement-context h3 { margin: 8px 0; font-size: 20px; font-weight: 600; }.movement-context p { display: flex; flex-wrap: wrap; gap: 16px; margin: 0; font-size: 13px; color: var(--erp-text-secondary); }.movement-context strong { font-weight: 500; }
</style>
