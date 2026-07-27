<script setup lang="ts">
import { computed } from 'vue'
import type {
  ProductionOverviewSummary,
  TagCard,
} from '../domain/types'
import { aggregateProductionOverviewRows } from '../domain/productionOverview'

const props = withDefaults(defineProps<{
  items?: TagCard[]
  loading: boolean
  summary?: ProductionOverviewSummary
  subtitle?: string
  pendingLabel?: string
  processingLabel?: string
  pendingQcLabel?: string
  completedLabel?: string
}>(), {
  items: () => [],
  summary: undefined,
  subtitle: '按当前配件和工艺统计',
  pendingLabel: '待打标记',
  processingLabel: '正在打标记',
  pendingQcLabel: '质检中',
  completedLabel: '已打完标记（累计合格）',
})

const pendingQuantity = computed(() => props.summary?.pendingQuantity ?? props.items
  .filter(item => item.tag_set_id === null)
  .reduce((sum, item) => sum + item.available_quantity, 0))

const processingRows = computed(() => props.summary?.processingRows ?? aggregateProductionOverviewRows(props.items.flatMap(item =>
  item.processing_details.map(detail => ({
    name: detail.tag_set_name,
    quantity: detail.quantity,
  })),
)))

const pendingQcRows = computed(() => props.summary?.pendingQcRows ?? aggregateProductionOverviewRows(props.items.map(item => ({
  name: item.tag_set_name,
  quantity: item.pending_qc_quantity,
}))))

const completedRows = computed(() => props.summary?.completedRows ?? aggregateProductionOverviewRows(props.items
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
      <span>{{ subtitle }}</span>
    </header>
    <div class="overview-grid">
      <article>
        <h4>{{ pendingLabel }}</h4>
        <strong class="total">{{ pendingQuantity }}</strong>
        <span>个</span>
      </article>
      <article>
        <h4>{{ processingLabel }}</h4>
        <div v-for="row in processingRows" :key="row.name" class="summary-row">
          <ElTag type="warning" effect="plain">{{ row.name }}</ElTag>
          <strong>{{ row.quantity }} 个</strong>
        </div>
        <span v-if="!processingRows.length" class="empty-text">暂无</span>
      </article>
      <article>
        <h4>{{ pendingQcLabel }}</h4>
        <div v-for="row in pendingQcRows" :key="row.name" class="summary-row">
          <ElTag type="info" effect="plain">{{ row.name }}</ElTag>
          <strong>{{ row.quantity }} 个</strong>
        </div>
        <span v-if="!pendingQcRows.length" class="empty-text">暂无</span>
      </article>
      <article>
        <h4>{{ completedLabel }}</h4>
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
.tag-production-overview { margin: 0 0 14px; padding: 14px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius); background: var(--md-surface-container-lowest); }
.tag-production-overview header { display: flex; align-items: baseline; gap: 10px; margin-bottom: 12px; }
.tag-production-overview header span, .empty-text { color: var(--el-text-color-secondary); font-size: 12px; }
.overview-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.overview-grid article { min-width: 0; padding: 11px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
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
