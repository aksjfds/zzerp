<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { DEPARTMENT_WORK_ORDER_OPERATE } from '@/permission/constants'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { printElement } from '@/shared/printing/printElement'
import ProductionDocumentSheet from './ProductionDocumentSheet.vue'
import {
  dispatchOutsource, queryOutsourceReceipts, returnOutsource,
  type OutsourceReceipt, type OutsourceDispatch, type OutsourceDispatchInput, type OutsourceInput,
} from '../api/outsourcing'

const props = defineProps<{ active: boolean; receiptId?: number; mode?: 'dispatch' | 'return' }>()
const emit = defineEmits<{ changed: []; close: [] }>()
const auth = useAuthStore()
const canOperate = computed(() => auth.user?.department_code === 'outsource' && auth.hasPermission(DEPARTMENT_WORK_ORDER_OPERATE))
const rows = ref<OutsourceReceipt[]>([]), page = ref(1), total = ref(0)
const loading = ref(false), error = ref(''), saving = ref(false), saveError = ref('')
const receipt = ref<OutsourceReceipt>(), dispatch = ref<OutsourceDispatch>()
const quantity = ref<number>(), process = ref<'etching' | 'plating'>('etching'), vendor = ref(''), note = ref('')
const draftSheet = ref<InstanceType<typeof ProductionDocumentSheet>>()
const printing = ref(false)
const documentFields = computed<[string, string | null, string?][]>(() => [
  ['产品', receipt.value?.product || ''], ['配件/装配体', receipt.value?.material || ''],
  ['委外工艺', null, 'process'], ['加工厂商', null, 'vendor'],
  ['外发数量', null, 'quantity'], ['备注', null, 'note'],
])
const draftFields = computed<[string, string | null][]>(() => [
  ['产品', receipt.value?.product || ''], ['配件/装配体', receipt.value?.material || ''],
  ['委外工艺', processName(process.value)], ['加工厂商', vendor.value.trim()],
  ['外发数量', quantity.value === undefined ? '' : String(quantity.value)], ['备注', note.value.trim()],
])
let active = true, revision = 0
let pending: { signature: string; requestId: string } | undefined
const limit = computed(() => !receipt.value ? 0 : dispatch.value
  ? remaining(dispatch.value.quantity, dispatch.value.returned_quantity)
  : remaining(receipt.value.quantity, receipt.value.dispatched_quantity))
function remaining(quantity: string, used: string) { return Number(BigInt(quantity) - BigInt(used)) }
function processName(value: string) { return value === 'etching' ? '蚀字' : '电镀' }
async function load() {
  const current = ++revision; loading.value = true; error.value = ''
  try {
    const result = await queryOutsourceReceipts(page.value, props.receiptId)
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 50) {
      page.value = Math.max(1, Math.ceil(result.total / 50)); await load(); return
    }
    rows.value = result.data; total.value = result.total
    if (props.receiptId) {
      if (!result.data[0]) { error.value = '交接票尚未登记有效委外到料'; return }
      const row = result.data[0]
      const batch = props.mode === 'return' ? row.dispatches.find(item => remaining(item.quantity, item.returned_quantity) > 0) : undefined
      if (props.mode === 'return' && !batch) { error.value = '没有待登记到料的外发单，请刷新交接票'; return }
      open(row, batch)
    }
  } catch (cause) {
    if (active && current === revision) { rows.value = []; error.value = getApiErrorDetail(cause)?.message || '委外加工加载失败' }
  } finally { if (active && current === revision) loading.value = false }
}
function open(row: OutsourceReceipt, batch?: OutsourceDispatch) {
  receipt.value = row; dispatch.value = batch; quantity.value = undefined
  process.value = 'etching'; vendor.value = ''; note.value = ''; saveError.value = ''; pending = undefined
}
const pendingDispatches = computed(() => receipt.value?.dispatches.filter(item => remaining(item.quantity, item.returned_quantity) > 0) || [])
function selectDispatch(id: number) {
  const batch = pendingDispatches.value.find(item => item.id === id)
  if (batch && receipt.value) open(receipt.value, batch)
}
function close() { if (!saving.value && !printing.value) { receipt.value = undefined; dispatch.value = undefined; emit('close') } }
function visibilityChanged(value: boolean) { if (!value) close() }
function validateForm() {
  if (!Number.isSafeInteger(quantity.value) || !quantity.value || quantity.value < 1 || quantity.value > limit.value) {
    saveError.value = `请输入 1 至 ${limit.value} 的整数数量`; return false
  }
  if (!dispatch.value && !vendor.value.trim()) { saveError.value = '请填写加工厂商'; return false }
  saveError.value = ''
  return true
}
async function printDraft() {
  if (saving.value || printing.value || dispatch.value || !receipt.value || !draftSheet.value?.element || !validateForm()) return
  printing.value = true
  try { await printElement(draftSheet.value.element, '外发单据') }
  catch (cause) { if (active) saveError.value = cause instanceof Error ? cause.message : '打印失败，请重试' }
  finally { if (active) printing.value = false }
}
async function save() {
  if (!receipt.value || !canOperate.value || saving.value || printing.value || !validateForm() || quantity.value === undefined) return
  const values = dispatch.value ? { dispatch_id: dispatch.value.id, quantity: quantity.value, note: note.value.trim() }
    : { receipt_id: receipt.value.id, quantity: quantity.value, note: note.value.trim(), process: process.value, vendor: vendor.value.trim() }
  const signature = JSON.stringify(values)
  if (!pending || pending.signature !== signature) pending = { signature, requestId: crypto.randomUUID() }
  const input: OutsourceInput = { quantity: quantity.value, note: note.value.trim(), request_id: pending.requestId }
  saving.value = true; saveError.value = ''
  try {
    if (dispatch.value) await returnOutsource(dispatch.value.id, input)
    else {
      const data: OutsourceDispatchInput = { ...input, receipt_id: receipt.value.id, process: process.value, vendor: vendor.value.trim() }
      await dispatchOutsource(data)
    }
    if (!active) return
    receipt.value = undefined; dispatch.value = undefined; emit('changed')
    if (props.receiptId) emit('close')
    else await load()
  } catch (cause) { if (active) saveError.value = getApiErrorDetail(cause)?.message || '登记失败，请重试' }
  finally { if (active) saving.value = false }
}
watch(() => props.active, value => { if (value) void load() })
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>

<template>
  <section class="outsourcing-panel">
    <div v-if="!receiptId" class="collection-heading"><h2>委外加工</h2><ElButton :loading="loading" @click="load">刷新</ElButton></div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElButton v-if="receiptId && error" @click="emit('close')">关闭</ElButton>
    <ElTable v-if="!error && !receiptId" v-loading="loading" :data="rows" row-key="id" empty-text="暂无已登记的委外到料">
      <ElTableColumn type="expand" width="44"><template #default="{ row }">
        <div class="processing-history">
          <ElEmpty v-if="!row.dispatches.length" description="尚未外发" :image-size="48" />
          <article v-for="batch in (row.dispatches as OutsourceDispatch[])" :key="batch.id" class="processing-batch">
            <div class="batch-heading"><strong>外发 #{{ batch.id }} · {{ processName(batch.process) }} · {{ batch.vendor }}</strong>
              <span class="batch-quantities">外发 <b>{{ batch.quantity }}</b> / 回料 <b class="returned">{{ batch.returned_quantity }}</b></span>
              <ElButton v-if="canOperate" link type="primary" :disabled="row.plan_status !== 'confirmed' || remaining(batch.quantity, batch.returned_quantity) <= 0" @click="open(row, batch)">登记到料</ElButton>
            </div>
            <p class="event-meta">{{ batch.actor_username }} · {{ batch.created_at }}<span v-if="batch.note"> · {{ batch.note }}</span></p>
            <ElTable :data="batch.returns" size="small" empty-text="等待厂商回料">
              <ElTableColumn class-name="returned-cell" prop="quantity" label="回料数量" width="120" align="right" />
              <ElTableColumn prop="actor_username" label="操作人" min-width="100" />
              <ElTableColumn prop="created_at" label="时间" min-width="180" />
              <ElTableColumn prop="note" label="备注" min-width="160" />
            </ElTable>
          </article>
        </div>
      </template></ElTableColumn>
      <ElTableColumn class-name="material-cell" prop="product" label="产品" min-width="180" />
      <ElTableColumn class-name="material-cell" prop="material" label="配件/装配体" min-width="220" />
      <ElTableColumn prop="order_no" label="订单号" min-width="160" />
      <ElTableColumn class-name="quantity-cell" prop="quantity" label="到料数量" width="120" align="right" />
      <ElTableColumn class-name="quantity-cell" prop="dispatched_quantity" label="已外发" width="120" align="right" />
      <ElTableColumn class-name="quantity-cell" label="待外发" width="120" align="right"><template #default="{ row }">{{ remaining(row.quantity, row.dispatched_quantity) }}</template></ElTableColumn>
      <ElTableColumn prop="created_at" label="到料时间" min-width="180" />
    </ElTable>
    <ElPagination v-if="!receiptId" v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
    <ElDialog :model-value="!!receipt" :title="dispatch ? '登记厂商到料' : '外发单据'" :width="dispatch ? 'min(560px, 94vw)' : 'min(760px, 96vw)'" align-center :close-on-click-modal="false" :close-on-press-escape="!saving && !printing" :show-close="!saving && !printing" @update:model-value="visibilityChanged">
      <template v-if="receipt">
        <div v-if="dispatch" class="dialog-context"><strong>{{ receipt.product }}</strong><div>{{ receipt.material }}</div><div>{{ receipt.order_no }}</div></div>
        <ElForm label-position="top" :disabled="saving || printing" @submit.prevent="save">
          <ProductionDocumentSheet v-if="!dispatch" title="外发单据" number="未外发" :fields="documentFields">
            <template #process><ElRadioGroup v-model="process" aria-label="委外工艺"><ElRadioButton value="etching">蚀字</ElRadioButton><ElRadioButton value="plating">电镀</ElRadioButton></ElRadioGroup></template>
            <template #vendor><ElInput v-model="vendor" aria-label="加工厂商" maxlength="100" /></template>
            <template #quantity><ElInputNumber v-model="quantity" aria-label="外发数量" :min="1" :max="Math.max(1, limit)" :disabled="limit <= 0" :precision="0" :step="1" step-strictly /><span class="available-quantity">可外发：{{ limit }}</span></template>
            <template #note><ElInput v-model="note" aria-label="备注" type="textarea" :rows="3" maxlength="1000" /></template>
          </ProductionDocumentSheet>
          <template v-else>
          <ElFormItem v-if="receiptId && mode === 'return' && dispatch" label="外发单" required>
            <ElSelect :model-value="dispatch.id" @change="selectDispatch"><ElOption v-for="batch in pendingDispatches" :key="batch.id" :value="batch.id" :label="`#${batch.id} · ${processName(batch.process)} · ${batch.vendor} · 待到料 ${remaining(batch.quantity, batch.returned_quantity)}`" /></ElSelect>
          </ElFormItem>
          <p>{{ processName(dispatch.process) }} · {{ dispatch.vendor }}</p>
          <ElFormItem :label="`${dispatch ? '到料' : '外发'}数量（最多 ${limit}）`" required><ElInputNumber v-model="quantity" :min="1" :max="Math.max(1, limit)" :disabled="limit <= 0" :precision="0" :step="1" step-strictly /></ElFormItem>
          <ElFormItem label="备注"><ElInput v-model="note" type="textarea" :rows="3" maxlength="1000" /></ElFormItem>
          </template>
          <ElAlert v-if="saveError" :title="saveError" type="error" :closable="false" show-icon />
        </ElForm>
        <div hidden aria-hidden="true"><ProductionDocumentSheet ref="draftSheet" title="外发单据" number="未外发" :fields="draftFields" /></div>
      </template>
      <template #footer><ElButton :disabled="saving || printing" @click="close">取消</ElButton><ElButton v-if="!dispatch" native-type="button" :loading="printing" :disabled="saving || limit <= 0" @click="printDraft">打印</ElButton><ElButton type="primary" :loading="saving" :disabled="printing || limit <= 0" @click="save">{{ dispatch ? '登记到料' : '确认外发' }}</ElButton></template>
    </ElDialog>
  </section>
</template>
<style scoped>
.outsourcing-panel { min-width: 0; }
.collection-heading, .batch-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.collection-heading { margin: 8px 0 24px; }.collection-heading h2 { margin: 0; color: var(--erp-text); font-size: 20px; font-weight: 600; }
.processing-history { padding: 24px; background: var(--erp-surface-muted); }
.processing-batch { padding: 24px; margin-bottom: 16px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }.processing-batch:last-child { margin-bottom: 0; }
.batch-heading > strong { font-size: 16px; font-weight: 600; color: var(--erp-text); overflow-wrap: anywhere; }.batch-quantities { font-size: 14px; color: var(--erp-text-secondary); }.batch-quantities b { margin: 0 4px; color: var(--erp-text); font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; }
.event-meta { margin: 12px 0 20px; color: var(--erp-text-secondary); font-size: 13px; line-height: 1.65; overflow-wrap: anywhere; }.returned, .batch-quantities .returned { color: var(--erp-success-strong); }
:deep(.material-cell) { font-weight: 600; }:deep(.quantity-cell) { font-weight: 600; font-variant-numeric: tabular-nums; }:deep(.returned-cell) { color: var(--erp-success-strong); font-weight: 600; font-variant-numeric: tabular-nums; }
.dialog-context { display: grid; gap: 6px; padding: 16px; margin-bottom: 24px; border: 1px solid var(--erp-border); border-radius: 8px; background: var(--erp-surface-muted); }.dialog-context strong { font-size: 16px; }.dialog-context div { color: var(--erp-text-secondary); font-size: 14px; line-height: 1.65; overflow-wrap: anywhere; }
.el-pagination { margin-top: 24px; max-width: 100%; overflow-x: auto; }
.available-quantity { display: inline-block; margin-left: 12px; color: var(--erp-text-secondary); font-size: 13px; }
:deep(.production-document-sheet .el-input-number) { max-width: 100%; }:deep(.production-document-sheet .el-radio-group) { white-space: normal; }
@media (max-width: 760px) { .processing-history { padding: 16px; }.processing-batch { padding: 16px; }.batch-heading { align-items: flex-start; }.batch-heading > strong { width: 100%; } }
</style>
