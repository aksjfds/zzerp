<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryQuality, type QualityBatch, type QualityEvent, type QualityRow } from '../api/quality'
import ProductionDocumentPrintDialog from './ProductionDocumentPrintDialog.vue'

const rows = ref<QualityBatch[]>([]), total = ref(0), page = ref(1)
const expanded = ref<number[]>([])
const statusLabels: Record<QualityBatch['status'], string> = {
  finished: '质检结束', awaiting_repair_receipt: '待接收返修', repairing: '返修中', awaiting_reinspection: '待复检',
}
type TimelineEntry = { key: string; title: string; kind: 'inspection' | 'repair'; events: QualityEvent[] }
function timelineEntries(events: QualityEvent[]) {
  const entries: TimelineEntry[] = [], repairs = new Map<number, TimelineEntry>()
  for (const event of events) {
    if (event.kind === 'inspection') {
      entries.push({ key: event.key, title: event.round === 0 ? '首次质检' : `第${event.round}次复检`, kind: 'inspection', events: [event] })
    } else {
      let entry = repairs.get(event.round)
      if (!entry) {
        entry = { key: `repair:${event.round}`, title: `第${event.round}次返修`, kind: 'repair', events: [] }
        repairs.set(event.round, entry)
        entries.push(entry)
      }
      entry.events.push(event)
    }
  }
  return entries
}
function batchSummary(batch: QualityBatch) {
  let good = 0n, scrap = 0n
  for (const event of batch.events) {
    if (!event.inspection) continue
    good += BigInt(event.inspection.good_quantity)
    scrap += BigInt(event.inspection.scrap_quantity)
  }
  return { good: String(good), scrap: String(scrap), unsettled: String(BigInt(batch.quantity) - good - scrap) }
}
const batches = computed(() => rows.value.map(batch => ({ ...batch, summary: batchSummary(batch), timeline: timelineEntries(batch.events) })))
const loading = ref(false), error = ref('')
const printRecord = ref<QualityRow>()
let active = true, revision = 0
async function load() {
  const current = ++revision; loading.value = true; error.value = ''
  try {
    const result = await queryQuality(page.value)
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 20) {
      page.value = Math.max(1, Math.ceil(result.total / 20)); await load(); return
    }
    rows.value = result.data; total.value = result.total
    expanded.value = expanded.value.filter(id => result.data.some(batch => batch.id === id))
  } catch (cause) { if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '质检记录加载失败' }
  finally { if (active && current === revision) loading.value = false }
}
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>
<template>
  <section class="quality-card">
    <div class="quality-toolbar"><h2>质检记录</h2><ElButton :loading="loading" @click="load">刷新</ElButton></div>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <div v-if="!error" v-loading="loading">
      <ElEmpty v-if="!loading && !rows.length" description="暂无质检记录" />
      <ElCollapse v-model="expanded" class="quality-batches">
        <ElCollapseItem v-for="batch in batches" :key="batch.id" :name="batch.id">
          <template #title><div class="batch-heading">
            <strong>{{ batch.product }}</strong><span>{{ batch.material }}</span>
            <span>订单 {{ batch.order_no }} · {{ batch.source_ref }} · 来料 {{ batch.quantity }}</span>
            <span class="batch-summary">总质检情况：<span class="quality-good">合格 <strong>{{ batch.summary.good }}</strong></span> / <span class="quality-scrap">报废 <strong>{{ batch.summary.scrap }}</strong></span> / <span class="quality-unsettled">未结 <strong>{{ batch.summary.unsettled }}</strong></span></span>
            <ElTag :type="batch.status === 'finished' ? 'success' : 'warning'">{{ statusLabels[batch.status] }}</ElTag>
          </div></template>
          <ElTimeline class="inspection-timeline">
            <ElTimelineItem v-for="entry in batch.timeline" :key="entry.key" :timestamp="entry.kind === 'inspection' ? entry.events[0]?.created_at : undefined" placement="top" :type="entry.kind === 'inspection' ? 'primary' : entry.events.some(event => event.kind === 'return') ? 'success' : 'warning'">
              <strong>{{ entry.title }}</strong>
              <div v-for="event in entry.events" :key="event.key" class="event-detail">
              <div class="event-heading"><span v-if="entry.kind === 'repair'">{{ event.kind === 'receive' ? '接收返修' : '回交QC' }} · {{ event.created_at }}</span><span>{{ event.department }} · {{ event.actor_username }}</span>
                <ElButton v-if="event.inspection" link type="primary" :disabled="loading" @click="printRecord = event.inspection">打印质检单</ElButton>
              </div>
              <div v-if="event.inspection" class="event-quantities">
                <span>质检 {{ event.quantity }}</span><span>合格 {{ event.inspection.good_quantity }}</span>
                <span>报废 {{ event.inspection.scrap_quantity }}</span><span>返修 {{ event.inspection.rework_quantity }}</span>
                <span v-if="event.inspection.repair_department">返修部门 {{ event.inspection.repair_department }} · {{ event.ticket_no }}</span>
              </div>
              <div v-else class="event-quantities"><span>{{ event.ticket_no }} · 数量 {{ event.quantity }}</span>
                <template v-if="event.kind === 'return'"><span>修好 {{ event.repaired_quantity }}</span><span>未修好 {{ event.unrepaired_quantity }}</span></template>
              </div>
              <p v-if="event.note" class="event-note">备注：{{ event.note }}</p>
              </div>
            </ElTimelineItem>
          </ElTimeline>
        </ElCollapseItem>
      </ElCollapse>
    </div>
    <ElPagination v-model:current-page="page" :total="total" :page-size="20" layout="prev, pager, next, total" @current-change="load" />
    <ProductionDocumentPrintDialog v-if="printRecord" :document="{ kind: 'quality', record: printRecord }" @close="printRecord = undefined" />
  </section>
</template>
<style scoped>
.quality-card { min-width: 0; padding: 24px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); }
.quality-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
h2 { margin: 0; font-size: 20px; font-weight: 700; }
.batch-heading { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; padding: 12px 0; text-align: left; line-height: 1.6; }
.batch-heading > span:not(.el-tag) { color: var(--erp-text-secondary); }
.batch-heading > span.batch-summary { color: var(--erp-text); font-variant-numeric: tabular-nums; }
.batch-heading > strong { flex-basis: 100%; font-size: 16px; color: var(--erp-text); }
.batch-summary strong { font-size: 17px; font-weight: 700; }
.quality-good { color: var(--erp-success-strong); }
.quality-scrap { color: var(--erp-danger-strong); }
.quality-unsettled { color: var(--erp-warning-strong); }
.event-heading strong, .inspection-timeline :deep(.el-timeline-item__content > strong) { color: var(--erp-text); font-size: 15px; }
.quality-batches :deep(.el-collapse-item__header) { height: auto; min-height: 56px; }
.inspection-timeline { padding: 16px 8px 0; }
.event-heading, .event-quantities { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; }
.event-heading > span { color: var(--erp-text-secondary); }
.event-detail { margin-top: 10px; }
.event-quantities { margin-top: 8px; font-variant-numeric: tabular-nums; }
.event-note { white-space: pre-wrap; overflow-wrap: anywhere; margin: 8px 0 0; color: var(--erp-text-secondary); }
.el-pagination { margin-top: 16px; }
@media (max-width: 760px) { .quality-card { padding: 16px; } }
</style>
