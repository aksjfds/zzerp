<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import type { HandoffTicket } from '../api/plans'
import { saveRework, type ReworkInput } from '../api/quality'

const props = defineProps<{ ticket: HandoffTicket }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const returning = props.ticket.action === 'rework_return'
const received = BigInt(props.ticket.received_quantity)
const limit = returning ? Number(received) : props.ticket.quantity
const quantity = ref(props.ticket.quantity), repaired = ref(0), unrepaired = ref(0), note = ref(''), saving = ref(false)
const partial = computed(() => !returning && quantity.value < props.ticket.quantity)
const summary = computed(() => `返修情况：修好 ${repaired.value}，未修好 ${unrepaired.value}`)
const requestId = crypto.randomUUID()
let active = true
onBeforeUnmount(() => { active = false })
async function save() {
  if (saving.value) return
  if (returning) {
    if ([repaired.value, unrepaired.value].some(value => !Number.isSafeInteger(value) || value < 0)
      || BigInt(repaired.value) + BigInt(unrepaired.value) !== received) {
      ElMessage.warning('修好数与未修好数之和必须等于实际接收数量'); return
    }
  } else if (!Number.isSafeInteger(quantity.value) || quantity.value < 1 || quantity.value > limit) {
    ElMessage.warning('接收数量须为不超过票面数量的正整数'); return
  }
  if (partial.value && !note.value.trim()) { ElMessage.warning('接收数量小于票面数量，必须填写备注'); return }
  const input: ReworkInput = { action: returning ? 'return' : 'receive', request_id: requestId, note: note.value.trim() }
  if (returning) { input.repaired_quantity = repaired.value; input.unrepaired_quantity = unrepaired.value }
  else input.quantity = quantity.value
  saving.value = true
  try {
    await saveRework(props.ticket.id, input)
    if (active) { ElMessage.success(returning ? '已回交QC，等待复检' : '返修到料已登记'); emit('saved') }
  } catch (cause) { if (active) ElMessage.error(getApiErrorDetail(cause)?.message || '返修登记失败') }
  finally { if (active) saving.value = false }
}
</script>
<template>
  <ElDialog :model-value="true" :title="returning ? '回交QC' : '接收返修'" width="min(520px, 94vw)" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @close="emit('close')">
    <p>{{ ticket.order_no }} · {{ ticket.factory_code }} · {{ ticket.product_name }}</p>
    <p>{{ ticket.material_no }} · {{ ticket.material_name }}</p>
    <p v-if="ticket.worker_name">返修工人：{{ ticket.worker_name }}</p>
    <p v-if="ticket.note">备注：{{ ticket.note }}</p>
    <p>{{ returning ? '实际接收数量' : '返修票数量' }}：{{ limit }}</p>
    <ElForm label-position="top" :disabled="saving" @submit.prevent="save">
      <template v-if="returning">
        <ElFormItem label="修好数量" required><ElInputNumber v-model="repaired" :min="0" :max="limit" :precision="0" /></ElFormItem>
        <ElFormItem label="未修好数量" required><ElInputNumber v-model="unrepaired" :min="0" :max="limit" :precision="0" /></ElFormItem>
      </template>
      <ElFormItem v-else label="接收数量" required><ElInputNumber v-model="quantity" :min="1" :max="limit" :precision="0" /></ElFormItem>
      <ElFormItem label="备注" :required="partial"><ElInput v-model="note" type="textarea" maxlength="2000" /></ElFormItem>
      <p v-if="returning">{{ summary }}</p>
      <ElButton type="primary" native-type="submit" :loading="saving">{{ returning ? '回交QC' : '登记到料' }}</ElButton>
    </ElForm>
  </ElDialog>
</template>
