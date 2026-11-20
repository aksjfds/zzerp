<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryWorkers, type WorkerResult, type WorkerTicket, type QualityRow } from '../api/quality'
import ProductionDocumentPrintDialog from './ProductionDocumentPrintDialog.vue'
const rows = ref<WorkerResult[]>([]), name = ref(''), page = ref(1), total = ref(0), loading = ref(false), error = ref('')
const selected = ref<WorkerTicket>(), printRecord = ref<QualityRow>()
let active = true, revision = 0
async function load() {
  const current = ++revision; loading.value = true; error.value = ''; rows.value = []
  try {
    const result = await queryWorkers(page.value, name.value)
    if (!active || current !== revision) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 20) { page.value = Math.max(1, Math.ceil(result.total / 20)); await load(); return }
    rows.value = result.data; total.value = result.total
  } catch (cause) { if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '工人计件结果加载失败' }
  finally { if (active && current === revision) loading.value = false }
}
function search() { page.value = 1; void load() }
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>
<template>
  <section class="worker-panel">
    <ElForm class="query-toolbar" inline label-position="top" @submit.prevent="search"><ElFormItem label="工人姓名"><ElInput v-model="name" clearable maxlength="100" /></ElFormItem><ElFormItem><ElButton type="primary" native-type="submit">查询</ElButton><ElButton :loading="loading" @click="load">刷新</ElButton></ElFormItem></ElForm>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <div v-if="!error" v-loading="loading"><ElEmpty v-if="!loading && !rows.length" description="暂无计件单" />
      <ElCollapse class="worker-records"><ElCollapseItem v-for="worker in rows" :key="worker.worker_name" :name="worker.worker_name">
        <template #title><div class="worker-summary"><strong>{{ worker.worker_name }}</strong><span>计件 <b>{{ worker.quantity }}</b></span><span>合格 <b class="good">{{ worker.good_quantity }}</b></span><span>报废 <b class="scrap">{{ worker.scrap_quantity }}</b></span><span>返修/未结 <b class="pending">{{ worker.unsettled_quantity }}</b></span></div></template>
        <ElTable :data="worker.tickets" row-key="id">
          <ElTableColumn prop="ticket_no" label="计件单" min-width="145" />
          <ElTableColumn prop="product" label="产品" min-width="180" />
          <ElTableColumn prop="material" label="配件/装配体" min-width="200" />
          <ElTableColumn prop="piecework_process" label="工艺" min-width="120" />
          <ElTableColumn class-name="quantity-cell" prop="quantity" label="计件数" width="100" align="right" />
          <ElTableColumn class-name="good-cell" prop="good_quantity" label="统计合格" width="100" align="right" />
          <ElTableColumn class-name="scrap-cell" prop="scrap_quantity" label="统计报废" width="100" align="right" />
          <ElTableColumn label="统计口径" min-width="170"><template #default="{ row }">{{ !row.events.length ? '待质检' : row.first_only ? '跨部门：仅首检' : '原工人：累计结果' }}</template></ElTableColumn>
          <ElTableColumn label="操作" width="110"><template #default="{ row }"><ElButton link type="primary" @click="selected = row">质检记录</ElButton></template></ElTableColumn>
        </ElTable>
      </ElCollapseItem></ElCollapse>
    </div>
    <ElPagination v-model:current-page="page" :page-size="20" :total="total" layout="prev, pager, next, total" @current-change="load" />
    <ElDialog :model-value="!!selected" title="计件单质检记录" width="min(760px, 96vw)" align-center @close="selected = undefined">
      <template v-if="selected"><p class="ticket-context">{{ selected.ticket_no }} · {{ selected.product }} · {{ selected.material }}</p><p>工艺：{{ selected.piecework_process || '—' }}</p><ElEmpty v-if="!selected.events.length" description="尚未质检" />
        <ElTimeline><ElTimelineItem v-for="event in selected.events.filter(item => item.kind === 'inspection')" :key="event.key" :timestamp="event.created_at" placement="top">
          <div class="inspection-record">
            <template v-if="event.inspection"><strong class="inspection-title">{{ event.round === 0 ? '首次质检' : '第' + event.round + '次复检' }}</strong><p class="inspection-quantities">质检 <b>{{ event.quantity }}</b> · 合格 <b class="good">{{ event.inspection.good_quantity }}</b> · 报废 <b class="scrap">{{ event.inspection.scrap_quantity }}</b> · 返修 <b class="pending">{{ event.inspection.rework_quantity }}</b></p><p class="record-meta">{{ event.actor_username }} · {{ event.note }}</p><p v-if="event.inspection.repair_kind">{{ event.inspection.repair_kind === 'original' ? '原部门原工人返修' : '跨部门返修（工人只计首检）' }} · {{ event.inspection.repair_department }} {{ event.inspection.repair_worker_name }}</p><ElButton link type="primary" @click="printRecord = event.inspection">打印质检单</ElButton></template>
            <div v-for="repair in selected.events.filter(item => item.kind !== 'inspection' && item.round === event.round + 1)" :key="repair.key" class="repair-record"><p><strong>{{ repair.kind === 'receive' ? '接收返修' : '回交QC' }} {{ repair.quantity }}</strong> · {{ repair.created_at }} · {{ repair.actor_username }}</p><p v-if="repair.kind === 'return'">修好 {{ repair.repaired_quantity }} / 未修好 {{ repair.unrepaired_quantity }}</p><p class="record-meta">{{ repair.note }}</p></div>
          </div>
        </ElTimelineItem></ElTimeline>
      </template>
    </ElDialog>
    <ProductionDocumentPrintDialog v-if="printRecord" :document="{ kind: 'quality', record: printRecord }" @close="printRecord = undefined" />
  </section>
</template>
<style scoped>
.worker-panel { min-width: 0; }
.worker-records { border: 0; }
.worker-records :deep(.el-collapse-item) { margin-bottom: 16px; border: 1px solid var(--erp-border); border-radius: 12px; overflow: hidden; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
.worker-records :deep(.el-collapse-item__header) { height: auto; min-height: 72px; padding: 0 24px; border-bottom: 0; }
.worker-records :deep(.el-collapse-item__wrap) { border-bottom: 0; }
.worker-records :deep(.el-collapse-item__content) { padding: 0 24px 24px; }
.worker-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 16px 24px; padding: 16px 0; line-height: 1.6; min-width: 0; }
.worker-summary > strong { color: var(--erp-text); font-size: 20px; font-weight: 600; margin-right: 16px; overflow-wrap: anywhere; }
.worker-summary > span { color: var(--erp-text-secondary); font-size: 14px; }
.worker-summary b { margin-left: 6px; color: var(--erp-text); font-size: 18px; font-weight: 600; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.good, .worker-summary .good { color: var(--erp-success-strong); }.scrap, .worker-summary .scrap { color: var(--erp-danger-strong); }.pending, .worker-summary .pending { color: var(--erp-warning-strong); }
:deep(.quantity-cell), :deep(.good-cell), :deep(.scrap-cell) { font-weight: 600; font-variant-numeric: tabular-nums; }:deep(.good-cell) { color: var(--erp-success-strong); }:deep(.scrap-cell) { color: var(--erp-danger-strong); }
.ticket-context { padding: 16px; border-radius: 8px; background: var(--erp-surface-muted); font-size: 16px; font-weight: 600; line-height: 1.65; overflow-wrap: anywhere; }
.inspection-record { padding: 16px; border: 1px solid var(--erp-border); border-radius: 12px; }.inspection-title { font-size: 16px; }.inspection-record p { margin: 10px 0; font-size: 14px; line-height: 1.65; overflow-wrap: anywhere; }.inspection-quantities b { font-size: 16px; font-variant-numeric: tabular-nums; }.record-meta { color: var(--erp-text-secondary); }.repair-record { margin-top: 16px; padding-top: 8px; border-top: 1px solid var(--erp-border); }.el-pagination { margin-top: 24px; max-width: 100%; overflow-x: auto; }
@media (max-width: 760px) { .worker-records :deep(.el-collapse-item__header) { padding: 0 16px; }.worker-records :deep(.el-collapse-item__content) { padding: 0 16px 16px; }.worker-summary { gap: 12px 16px; }.worker-summary > strong { width: 100%; margin: 0; } }
</style>
