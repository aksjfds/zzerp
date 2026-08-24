<script setup lang="ts">
import { computed } from 'vue'
import type { ProductionNodeStat } from './productionProgress'
import type { FlowNodeType } from './types'
import {
  formatQuantity,
  inputDetails as buildInputDetails,
  nodeStatus as buildNodeStatus,
  nodeTypeLabel,
  primaryProgress as buildPrimaryProgress,
  progressFields as buildProgressFields,
} from './productionViewerModel'

const props = defineProps<{
  label: string
  type?: FlowNodeType
  stat: ProductionNodeStat | null
}>()
const nodeStatus = computed(() => buildNodeStatus(props.stat, props.type))
const primaryProgress = computed(() => buildPrimaryProgress(props.stat, props.type))
const progressFields = computed(() => buildProgressFields(props.stat, props.type))
const inputDetails = computed(() => buildInputDetails(props.stat))
</script>

<template>
  <div class="node-progress-popover">
    <div class="node-progress-header">
      <div><div class="node-progress-title">{{ label }}</div><div class="node-progress-type">{{ nodeTypeLabel(type) }}</div></div>
      <span class="node-progress-status" :class="`is-${nodeStatus.tone}`">{{ nodeStatus.label }}</span>
    </div>
    <template v-if="stat">
      <div class="node-progress-primary"><span>{{ primaryProgress.label }}</span><strong>{{ formatQuantity(primaryProgress.value) }}</strong></div>
      <div class="node-progress-grid">
        <template v-for="field in progressFields" :key="field.label">
          <span>{{ field.label }}</span>
          <strong :class="{ 'is-danger': field.danger, 'is-zero': field.value === 0 }">{{ formatQuantity(field.value) }}</strong>
        </template>
      </div>
      <details v-if="inputDetails.length" class="node-input-details">
        <summary>来源明细（{{ inputDetails.length }}）</summary>
        <div class="node-input-list">
          <template v-for="item in inputDetails" :key="item.name"><span>{{ item.name }}</span><strong>{{ formatQuantity(item.quantity) }}</strong></template>
        </div>
      </details>
    </template>
    <div v-else class="node-progress-empty">暂无生产记录</div>
  </div>
</template>

<style scoped>
.node-progress-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.node-progress-title { color: var(--el-text-color-primary); font-size: 16px; font-weight: 700; line-height: 1.35; }
.node-progress-type { margin-top: 3px; color: var(--el-text-color-secondary); font-size: 12px; }
.node-progress-status { flex: none; padding: 3px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.node-progress-status.is-pending { color: var(--el-text-color-secondary); background: var(--md-surface-container); }
.node-progress-status.is-active { color: var(--erp-warning); background: color-mix(in srgb, var(--erp-warning) 12%, transparent); }
.node-progress-status.is-done { color: var(--erp-success); background: color-mix(in srgb, var(--erp-success) 12%, transparent); }
.node-progress-status.is-danger { color: var(--el-color-danger); background: color-mix(in srgb, var(--el-color-danger) 12%, transparent); }
.node-progress-primary { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-top: 14px; padding: 12px 14px; border-radius: 10px; background: var(--md-surface-container-low); }
.node-progress-primary span { color: var(--el-text-color-secondary); font-size: 13px; }
.node-progress-primary strong { color: var(--el-color-primary); font-size: 24px; font-variant-numeric: tabular-nums; line-height: 1; }
.node-progress-grid { display: grid; grid-template-columns: 1fr auto; gap: 9px 20px; margin-top: 14px; padding: 0 2px; }
.node-progress-grid span { color: var(--el-text-color-secondary); }
.node-progress-grid strong { color: var(--el-text-color-primary); font-variant-numeric: tabular-nums; text-align: right; }
.node-progress-grid strong.is-zero { color: var(--el-text-color-placeholder); font-weight: 500; }
.node-progress-grid strong.is-danger { color: var(--el-color-danger); font-weight: 700; }
.node-input-details { margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--md-outline-variant); }
.node-input-details summary { color: var(--el-text-color-regular); cursor: pointer; font-size: 13px; font-weight: 600; }
.node-input-list { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 7px 16px; margin-top: 10px; }
.node-input-list span { overflow: hidden; color: var(--el-text-color-secondary); text-overflow: ellipsis; white-space: nowrap; }
.node-input-list strong { font-variant-numeric: tabular-nums; text-align: right; }
.node-progress-empty { margin-top: 14px; padding: 18px 12px; border-radius: 10px; color: var(--el-text-color-secondary); background: var(--md-surface-container-low); text-align: center; }
</style>
