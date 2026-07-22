<script setup lang="ts">
import { computed } from 'vue'
import type { TagCard } from '../domain/types'

const props = defineProps<{
  items: TagCard[]
  loading: boolean
}>()

type SummaryRow = { name: string; quantity: number }

function aggregate(rows: SummaryRow[]) {
  const quantities = new Map<string, number>()
  rows.forEach(row => quantities.set(row.name, (quantities.get(row.name) || 0) + row.quantity))
  return [...quantities.entries()]
    .filter(([, quantity]) => quantity > 0)
    .map(([name, quantity]) => ({ name, quantity }))
}

const untaggedQuantity = computed(() => props.items
  .filter(item => item.tag_set_id === null)
  .reduce((sum, item) => sum + item.available_quantity, 0))

const processingRows = computed(() => aggregate(props.items.flatMap(item =>
  item.processing_details.map(detail => ({
    name: detail.tag_set_name,
    quantity: detail.quantity,
  })),
)))

const pendingQcRows = computed(() => aggregate(props.items.map(item => ({
  name: item.tag_set_name,
  quantity: item.pending_qc_quantity,
}))))

const completedRows = computed(() => aggregate(props.items
  .filter(item => item.tag_set_id !== null)
  .map(item => ({
    name: item.tag_set_name,
    quantity: item.completed_quantity,
  }))))
</script>

<template>
  <section v-loading="loading" class="tag-production-overview">
    <header>
      <strong>配件生产情况</strong>
      <span>按当前配件和工艺统计</span>
    </header>
    <div class="overview-grid">
      <article>
        <h4>待打标记</h4>
        <strong class="total">{{ untaggedQuantity }}</strong>
        <span>个</span>
      </article>
      <article>
        <h4>正在打标记</h4>
        <div v-for="row in processingRows" :key="row.name" class="summary-row">
          <ElTag type="warning" effect="plain">{{ row.name }}</ElTag>
          <strong>{{ row.quantity }} 个</strong>
        </div>
        <span v-if="!processingRows.length" class="empty-text">暂无</span>
      </article>
      <article>
        <h4>质检中</h4>
        <div v-for="row in pendingQcRows" :key="row.name" class="summary-row">
          <ElTag type="info" effect="plain">{{ row.name }}</ElTag>
          <strong>{{ row.quantity }} 个</strong>
        </div>
        <span v-if="!pendingQcRows.length" class="empty-text">暂无</span>
      </article>
      <article>
        <h4>已打完标记（累计合格）</h4>
        <div v-for="row in completedRows" :key="row.name" class="summary-row">
          <ElTag type="success" effect="plain">{{ row.name }}</ElTag>
          <strong>{{ row.quantity }} 个</strong>
        </div>
        <span v-if="!completedRows.length" class="empty-text">暂无</span>
      </article>
    </div>
  </section>
</template>

<style scoped>
.tag-production-overview { margin: 14px 0; padding: 14px; border: 1px solid var(--erp-border); border-radius: 8px; background: #fff; }
.tag-production-overview header { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; }
.tag-production-overview header span, .empty-text { color: var(--el-text-color-secondary); font-size: 12px; }
.overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.overview-grid article { min-width: 0; padding: 11px; border-radius: 7px; background: #f8fafc; }
.overview-grid h4 { margin: 0 0 9px; color: var(--el-text-color-secondary); font-size: 12px; font-weight: 500; }
.total { font-size: 22px; }
.overview-grid article > span:not(.empty-text) { margin-left: 4px; color: var(--el-text-color-secondary); font-size: 12px; }
.summary-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.summary-row + .summary-row { margin-top: 7px; }
.summary-row :deep(.el-tag) { min-width: 0; max-width: calc(100% - 54px); }
.summary-row :deep(.el-tag__content) { overflow: hidden; text-overflow: ellipsis; }
.summary-row strong { flex: none; font-size: 13px; }
@media (max-width: 1180px) { .overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .overview-grid { grid-template-columns: 1fr; } }
</style>
