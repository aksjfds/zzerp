<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { printElement } from '@/shared/printing/printElement'
import type { DepartmentLedgerMovement, HandoffTicket } from '../api/plans'
import type { WarehousePick } from '../api/warehouse'
import type { QualityRow } from '../api/quality'
import ProductionDocumentSheet from './ProductionDocumentSheet.vue'

const props = defineProps<{ inline?: boolean; document: { kind: 'handoff'; record: HandoffTicket } | { kind: 'quality'; record: QualityRow } | { kind: 'issue'; record: DepartmentLedgerMovement } | { kind: 'warehouse'; record: WarehousePick } }>()
const emit = defineEmits<{ close: [] }>()
const sheet = ref<HTMLElement>()
const printing = ref(false)
const title = computed(() => {
  const doc = props.document
  if (doc.kind === 'quality') return 'QC质检单'
  const type = doc.kind === 'handoff'
    ? { normal: '普通交接', rework: '返修交接', return: '返修回交', warehouse: '仓库出料' }[doc.record.kind]
    : doc.kind === 'warehouse' ? '仓库出料' : '普通交接'
  return `物料交接单 - ${type}`
})
const number = computed(() => {
  const doc = props.document
  if (doc.kind === 'handoff' || doc.kind === 'issue') return doc.record.ticket_no
  return `${doc.kind === 'quality' ? 'QC' : 'WL'}-${String(doc.record.id).padStart(8, '0')}`
})
const fields = computed<[string, string | null][]>(() => {
  const doc = props.document
  if (doc.kind === 'issue') {
    const row = doc.record
    return [['产品', `${row.factory_code} · ${row.product_name}`],
      ['配件/装配体', `${row.material_no} · ${row.material_name}`],
      ['交接', `${row.source_department || '—'} -> ${row.target_department || '—'}，${row.quantity}`],
      ['出料人', row.actor_username], ['备注', row.note]]
  }
  if (doc.kind === 'warehouse') {
    const row = doc.record
    return [['产品', row.product], ['配件/装配体', row.material],
      ['交接', `仓库部 -> ${row.department}，${row.quantity}`], ['出料人', row.actor_username], ['备注', row.note]]
  }
  if (doc.kind === 'handoff') {
    const row = doc.record
    return [
      ['产品', `${row.factory_code} · ${row.product_name}`], ['配件/装配体', `${row.material_no} · ${row.material_name}`],
      ['交接', `${row.source_department} -> ${row.target_department}，${row.quantity}`], ['备注', row.note],
    ]
  }
  const row = doc.record
  return [
    ['来源单据', row.source_ref], ['产品', row.product], ['配件/装配体', row.material], ['订单号', row.order_no],
    ['质检部门', row.department], ['质检数量', row.quantity], ['合格数量', row.good_quantity],
    ['报废数量', row.scrap_quantity], ['返修数量', row.rework_quantity], ['返修部门', row.repair_department],
    ['操作人', row.actor_username], ['质检时间', row.created_at], ['备注', row.note],
  ]
})
let active = true
onBeforeUnmount(() => { active = false })
async function print() {
  if (!sheet.value || printing.value) return
  printing.value = true
  try { await printElement(sheet.value, `${title.value}-${number.value}`) }
  catch (cause) { if (active) ElMessage.error(cause instanceof Error ? cause.message : '打印失败，请重试') }
  finally { if (active) printing.value = false }
}
defineExpose({ print })
</script>

<template>
  <div v-if="inline" ref="sheet"><ProductionDocumentSheet :title="title" :number="number" :fields="fields" :time="document.kind === 'quality' ? undefined : document.record.created_at" :quality="document.kind === 'quality'" /></div>
  <ElDialog v-else :model-value="true" :title="title" width="min(760px, 96vw)" :close-on-click-modal="!printing" :close-on-press-escape="!printing" :show-close="!printing" @close="emit('close')">
    <div ref="sheet"><ProductionDocumentSheet :title="title" :number="number" :fields="fields" :time="document.kind === 'quality' ? undefined : document.record.created_at" :quality="document.kind === 'quality'" /></div>
    <template #footer><ElButton :disabled="printing" @click="emit('close')">关闭</ElButton><ElButton type="primary" :loading="printing" @click="print">打印</ElButton></template>
  </ElDialog>
</template>

