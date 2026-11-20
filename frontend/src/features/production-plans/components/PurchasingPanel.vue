<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { DEPARTMENT_WORK_ORDER_OPERATE } from '@/permission/constants'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import DepartmentMovementDialog from './DepartmentMovementDialog.vue'
import { createPurchase, queryPurchaseWorkOrders, receivePurchase, type PurchaseInput, type PurchaseRecord, type PurchaseWorkOrder } from '../api/purchasing'

const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const canOperate = computed(() => auth.user?.department_code === 'warehouse' && auth.hasPermission(DEPARTMENT_WORK_ORDER_OPERATE))
const rows = ref<PurchaseWorkOrder[]>([]), page = ref(1), total = ref(0), loading = ref(false), error = ref('')
const expanded = ref<number[]>([])
const selected = ref<PurchaseWorkOrder>(), purchase = ref<PurchaseRecord>(), issuing = ref<PurchaseWorkOrder>()
const quantity = ref<number>(), note = ref(''), saving = ref(false), saveError = ref('')
let active = true, revision = 0
defineExpose({ refresh: () => load() })
let pending: { signature: string; input: PurchaseInput } | undefined
async function load() {
  const current = ++revision; loading.value = true; error.value = ''
  try {
    const result = await queryPurchaseWorkOrders(page.value)
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 50) {
      page.value = Math.max(1, Math.ceil(result.total / 50)); await load(); return
    }
    rows.value = result.data; total.value = result.total
  } catch (cause) { if (active && current === revision) { rows.value = []; error.value = getApiErrorDetail(cause)?.message || '采购工单加载失败' } }
  finally { if (active && current === revision) loading.value = false }
}
function open(row: PurchaseWorkOrder, record?: PurchaseRecord) {
  if (!canOperate.value || row.plan_status !== 'confirmed' || record?.received) return
  selected.value = row; purchase.value = record; quantity.value = undefined; note.value = ''; saveError.value = ''; pending = undefined
  expanded.value = [...new Set([...expanded.value, row.id])]
}
function expandChanged(_row: PurchaseWorkOrder, records: PurchaseWorkOrder[]) { expanded.value = records.map(row => row.id) }
function close() { if (!saving.value) { selected.value = undefined; purchase.value = undefined } }
function visibilityChanged(value: boolean) { if (!value) close() }
async function changed() { emit('changed'); await load() }
async function save() {
  if (!selected.value || !canOperate.value || saving.value) return
  if (!Number.isSafeInteger(quantity.value) || !quantity.value || quantity.value < 1) { saveError.value = '请输入正整数数量'; return }
  if (purchase.value && quantity.value > Number(purchase.value.quantity)) { saveError.value = '到料不能超过采购数量'; return }
  if (purchase.value && quantity.value < Number(purchase.value.quantity) && !note.value.trim()) { saveError.value = '少到料必须填写备注'; return }
  const value = { quantity: quantity.value, note: note.value.trim() }
  const signature = JSON.stringify({ ...value, order: selected.value.id, purchase: purchase.value?.id })
  if (!pending || pending.signature !== signature) pending = { signature, input: { ...value, request_id: crypto.randomUUID() } }
  saving.value = true; saveError.value = ''
  try {
    if (purchase.value) await receivePurchase(purchase.value.id, pending.input)
    else await createPurchase(selected.value.id, pending.input)
    if (!active) return
    selected.value = undefined; purchase.value = undefined; await changed()
  } catch (cause) { if (active) saveError.value = getApiErrorDetail(cause)?.message || '采购登记失败' }
  finally { if (active) saving.value = false }
}
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>

<template>
  <section class="purchasing-panel">
    <div class="collection-heading"><h2>外购件采购</h2><ElButton :loading="loading" @click="load">刷新</ElButton></div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" row-key="id" :expand-row-keys="expanded" empty-text="暂无外购节点工单" @expand-change="expandChanged">
      <ElTableColumn type="expand" width="44"><template #default="{ row }"><div class="purchase-records"><ElTable :data="row.purchases" row-key="id" empty-text="尚未采购">
        <ElTableColumn label="采购记录" width="120"><template #default="{ row: record }">#{{ record.id }}</template></ElTableColumn>
        <ElTableColumn prop="quantity" label="采购数量" width="120" align="right" /><ElTableColumn prop="received_quantity" label="到料数量" width="120" align="right" />
        <ElTableColumn prop="actor_username" label="操作人" min-width="100" /><ElTableColumn prop="created_at" label="采购时间" min-width="180" />
        <ElTableColumn label="操作" width="120"><template #default="{ row: record }"><ElButton v-if="canOperate" link type="primary" :disabled="record.received || row.plan_status !== 'confirmed'" @click="open(row, record)">{{ record.received ? '已登记到料' : '登记到料' }}</ElButton></template></ElTableColumn>
        <ElTableColumn prop="note" label="备注" min-width="160" />
      </ElTable></div></template></ElTableColumn>
      <ElTableColumn label="产品" min-width="180"><template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template></ElTableColumn>
      <ElTableColumn label="配件/装配体" min-width="220"><template #default="{ row }">{{ row.part_no }} · {{ row.part_name }}</template></ElTableColumn>
      <ElTableColumn prop="order_no" label="订单号" min-width="160" />
      <ElTableColumn label="上游/下游" min-width="180"><template #default="{ row }">{{ row.upstream_departments.join('、') || '—' }} / {{ row.downstream_departments.join('、') || '—' }}</template></ElTableColumn>
      <ElTableColumn prop="order_quantity" label="订单数量" width="110" align="right" /><ElTableColumn prop="task_quantity" label="任务数量" width="120" align="right" />
      <ElTableColumn label="累积到料/累计出料" min-width="170" align="right"><template #default="{ row }">{{ row.received_quantity }}/{{ row.issued_quantity }}</template></ElTableColumn>
      <ElTableColumn label="操作" min-width="150"><template #default="{ row }"><ElButton v-if="canOperate" link type="primary" :disabled="row.plan_status !== 'confirmed'" @click="open(row)">采购</ElButton><ElButton v-if="canOperate && row.can_issue" link type="primary" :disabled="row.plan_status !== 'confirmed' || BigInt(row.received_quantity) <= BigInt(row.issued_quantity)" @click="issuing = row">出料</ElButton></template></ElTableColumn>
    </ElTable>
    <ElPagination v-model:current-page="page" :total="total" :page-size="50" layout="prev, pager, next, total" @current-change="load" />
    <ElDialog :model-value="!!selected" :title="purchase ? '采购到料登记' : '采购'" width="min(480px, 94vw)" align-center :show-close="!saving" :close-on-click-modal="false" :close-on-press-escape="!saving" @update:model-value="visibilityChanged">
      <template v-if="selected"><div class="purchase-context"><strong>{{ selected.factory_code }} · {{ selected.product_name }}</strong><div>{{ selected.part_no }} · {{ selected.part_name }}</div><div>{{ selected.order_no }}</div><div v-if="purchase">采购 #{{ purchase.id }} · 采购数量 {{ purchase.quantity }}</div></div>
        <ElForm label-position="top" :disabled="saving" @submit.prevent="save"><ElFormItem :label="purchase ? '本次到料数量' : '采购数量'" required><ElInputNumber v-model="quantity" :min="1" :max="purchase ? Number(purchase.quantity) : Number.MAX_SAFE_INTEGER" :precision="0" controls-position="right" /></ElFormItem><ElFormItem label="备注"><ElInput v-model="note" type="textarea" :rows="3" maxlength="1000" /></ElFormItem></ElForm><ElAlert v-if="saveError" :title="saveError" type="error" :closable="false" show-icon />
      </template><template #footer><ElButton :disabled="saving" @click="close">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">{{ purchase ? '登记到料' : '确认采购' }}</ElButton></template>
    </ElDialog>
    <DepartmentMovementDialog v-if="issuing" :order="issuing" direction="issue" @close="issuing = undefined" @changed="changed" />
  </section>
</template>

<style scoped>
.purchasing-panel { min-width: 0; padding: 24px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }.collection-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 20px; }h2 { margin: 0; font-size: 20px; font-weight: 600; }.purchase-records { padding: 16px; background: var(--erp-surface-muted); }.purchase-context { display: grid; gap: 8px; margin-bottom: 20px; overflow-wrap: anywhere; }.el-pagination { margin-top: 20px; max-width: 100%; overflow-x: auto; }@media (max-width: 760px) { .purchasing-panel { padding: 16px; } }
</style>
