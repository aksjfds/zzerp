<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { dispatchWarehouse, queryDispatchPlans, queryDispatchTargets, type WarehouseStock, type WarehouseDispatchPlan, type WarehouseDispatchTarget } from '../api/warehouse'
import { printElement } from '@/shared/printing/printElement'
import ProductionDocumentSheet from './ProductionDocumentSheet.vue'

const props = defineProps<{ stocks: WarehouseStock[] }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const stockId = ref<number | undefined>(props.stocks.length === 1 ? props.stocks[0]?.id : undefined), planId = ref<number>(), targetId = ref<number>()
const plans = ref<WarehouseDispatchPlan[]>([]), targets = ref<WarehouseDispatchTarget[]>([])
const planLoading = ref(false), targetLoading = ref(false), saving = ref(false), error = ref('')
const quantity = ref(1), note = ref('')
const stockChoices = computed(() => [...new Map(props.stocks.map(stock => [`${stock.product_id}:${stock.material_key}`, stock])).values()])
const stock = computed(() => stockChoices.value.find(item => item.id === stockId.value))
const target = computed(() => targets.value.find(item => item.target_order_id === targetId.value))
const limit = computed(() => Math.min(Number(target.value?.available_quantity || 0), Number.MAX_SAFE_INTEGER))
const requestId = crypto.randomUUID()
const savedPickId = ref<number>()
const printing = ref(false)
const draftSheet = ref<InstanceType<typeof ProductionDocumentSheet>>()
const documentFields = computed<[string, string | null, string?][]>(() => [
  ['产品', stock.value?.product || '请选择库存物料'], ['配件/装配体', stock.value?.material || '—'],
  ['交接', null, 'handoff'], ['备注', null, 'note'],
])
const draftFields = computed<[string, string | null][]>(() => [
  ['产品', stock.value?.product || '—'], ['配件/装配体', stock.value?.material || '—'],
  ['交接', `仓库部 -> ${target.value?.department || '—'}，${quantity.value}`], ['备注', note.value.trim()],
])
let active = true, planSequence = 0, targetSequence = 0
function close() { if (savedPickId.value) emit('saved'); else emit('close') }
async function printDraft() {
  if (printing.value || saving.value || !draftSheet.value?.element) return
  if (!stock.value || !target.value || !Number.isSafeInteger(quantity.value) || quantity.value < 1) {
    ElMessage.warning('请选择物料及接收部门，填写正整数数量'); return
  }
  printing.value = true
  try {
    await printElement(draftSheet.value.element, '物料交接单 - 仓库出料')
  } catch (cause) { if (active) ElMessage.error(cause instanceof Error ? cause.message : '打印失败，请重试') }
  finally { if (active) printing.value = false }
}
async function loadPlans(keyword = '') {
  const current = ++planSequence, selected = stock.value
  if (!selected) return
  planLoading.value = true; error.value = ''
  try { const result = await queryDispatchPlans(selected.id, keyword); if (active && current === planSequence) plans.value = result }
  catch (cause) { if (active && current === planSequence) error.value = getApiErrorDetail(cause)?.message || '目标订单加载失败' }
  finally { if (active && current === planSequence) planLoading.value = false }
}
function changeStock() {
  planId.value = undefined; targetId.value = undefined; plans.value = []; targets.value = []
  targetSequence += 1; targetLoading.value = false
  void loadPlans()
}
async function loadTargets() {
  const current = ++targetSequence, selected = stock.value, plan = planId.value
  targets.value = []; targetId.value = undefined
  if (!selected || !plan) return
  targetLoading.value = true; error.value = ''
  try { const result = await queryDispatchTargets(selected.id, plan); if (active && current === targetSequence) targets.value = result }
  catch (cause) { if (active && current === targetSequence) error.value = getApiErrorDetail(cause)?.message || '下游工单加载失败' }
  finally { if (active && current === targetSequence) targetLoading.value = false }
}
async function save() {
  if (saving.value || printing.value || savedPickId.value) return
  if (planLoading.value || targetLoading.value || error.value) return
  if (!stock.value || !target.value || !Number.isSafeInteger(quantity.value) || quantity.value < 1 || quantity.value > limit.value) {
    ElMessage.warning('请选择库存和下游工单，填写不超过库存的正整数数量'); return
  }
  saving.value = true
  try {
    const result = await dispatchWarehouse(stock.value, target.value, quantity.value, requestId, note.value.trim())
    if (active) {
      savedPickId.value = result.id
      ElMessage.success('仓库出料已登记')
      emit('saved')
    }
  } catch (cause) { if (active) ElMessage.error(getApiErrorDetail(cause)?.message || '出料失败，请刷新库存后重试') }
  finally { if (active) saving.value = false }
}
onMounted(() => { if (stock.value) void loadPlans() })
onBeforeUnmount(() => { active = false; planSequence += 1; targetSequence += 1 })
</script>
<template>
  <ElDialog :model-value="true" title="物料交接单" width="min(760px, 96vw)" :close-on-click-modal="!saving && !printing" :close-on-press-escape="!saving && !printing" :show-close="!saving && !printing" @close="close">
    <LoadErrorAlert :message="error" :loading="planLoading || targetLoading" @retry="stock && (planId ? loadTargets() : loadPlans())" />
    <ElForm label-position="top" :disabled="saving || printing || !!savedPickId" @submit.prevent="save()">
      <ElFormItem v-if="stockChoices.length > 1" label="库存物料" required><ElSelect v-model="stockId" filterable placeholder="选择本页库存物料" @change="changeStock"><ElOption v-for="item in stockChoices" :key="item.id" :value="item.id" :label="`${item.product} · ${item.material}`" /></ElSelect></ElFormItem>
      <ElFormItem label="目标订单" required><ElSelect v-model="planId" filterable remote :remote-method="loadPlans" :loading="planLoading" :disabled="!stock" placeholder="搜索已确认订单号" @change="loadTargets"><ElOption v-for="item in plans" :key="item.id" :value="item.id" :label="item.order_no" /></ElSelect></ElFormItem>
      <ProductionDocumentSheet title="物料交接单 - 仓库出料" :fields="documentFields">
        <template #handoff><div class="handoff-inputs"><span>仓库部 -&gt;</span>
          <ElSelect v-model="targetId" aria-label="接收部门" :loading="targetLoading" :disabled="!planId || targetLoading" placeholder="选择接收部门" no-data-text="此订单无匹配的下游工单"><ElOption v-for="item in targets" :key="item.target_order_id" :value="item.target_order_id" :label="`${item.department} · ${item.material}`" /></ElSelect><span>，</span>
          <ElInputNumber v-model="quantity" aria-label="交接数量" :min="1" :max="Math.max(1, limit)" :precision="0" :disabled="!target || limit < 1" />
        </div></template>
        <template #note><ElInput v-model="note" aria-label="备注" type="textarea" :rows="3" maxlength="1000" show-word-limit /></template>
      </ProductionDocumentSheet>
      <p v-if="target">可出料数量：{{ target.available_quantity }}</p>
    </ElForm>
    <div hidden><ProductionDocumentSheet ref="draftSheet" title="物料交接单 - 仓库出料" :fields="draftFields" /></div>
    <template #footer><ElButton :disabled="saving || printing" @click="close">关闭</ElButton><ElButton :loading="saving" :disabled="printing || !target || limit < 1 || planLoading || targetLoading || !!error" @click="save()">出料</ElButton><ElButton type="primary" :loading="printing" :disabled="saving || !target || planLoading || targetLoading || !!error" @click="printDraft">打印</ElButton></template>
  </ElDialog>
</template>
<style scoped>
.handoff-inputs { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.handoff-inputs .el-select { flex: 1 1 150px; min-width: 130px; }
</style>
