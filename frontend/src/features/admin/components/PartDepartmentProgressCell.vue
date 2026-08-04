<script setup lang="ts">
import { computed } from 'vue'
import type { PmcPartDepartmentProgress } from '../domain/pmcPartProgress'

const props = defineProps<{
  item?: PmcPartDepartmentProgress
  departmentCode: string
}>()

const state = computed(() => {
  const item = props.item
  if (!item?.in_route) return { label: '—', type: 'info' as const }
  if (item.scrap_quantity || item.lost_quantity) {
    return { label: '存在异常', type: 'danger' as const }
  }
  if (item.pending_qc_quantity) {
    return { label: props.departmentCode === 'qc' ? '待质检' : '质检中', type: 'warning' as const }
  }
  if (item.processing_quantity) return { label: '加工中', type: 'warning' as const }
  if (item.waiting_quantity) {
    return {
      label: props.departmentCode === 'qc' ? '合格待放行' : '待处理',
      type: 'primary' as const,
    }
  }
  if (item.completed_quantity) return { label: '已转出', type: 'success' as const }
  return { label: '未到达', type: 'info' as const }
})
</script>

<template>
  <div v-if="item?.in_route" class="progress-cell">
    <div class="cell-heading">
      <ElTag :type="state.type" effect="plain" size="small">{{ state.label }}</ElTag>
    </div>
    <div class="quantity-list">
      <span v-if="item.waiting_quantity">待处理 <b>{{ item.waiting_quantity }}</b></span>
      <span v-if="item.processing_quantity">加工中 <b>{{ item.processing_quantity }}</b></span>
      <span v-if="item.pending_qc_quantity">待检 <b>{{ item.pending_qc_quantity }}</b></span>
      <span v-if="item.completed_quantity">已转出 <b>{{ item.completed_quantity }}</b></span>
      <span v-if="item.scrap_quantity" class="danger">报废 <b>{{ item.scrap_quantity }}</b></span>
      <span v-if="item.lost_quantity" class="danger">遗失 <b>{{ item.lost_quantity }}</b></span>
    </div>
  </div>
  <span v-else class="not-in-route">—</span>
</template>

<style scoped>
.progress-cell { display: grid; min-width: 160px; gap: 7px; padding: 3px 0; }
.cell-heading { display: flex; min-width: 0; align-items: center; }
.quantity-list { display: flex; flex-wrap: wrap; gap: 4px 10px; font-size: 12px; }
.quantity-list span { color: var(--el-text-color-secondary); }
.quantity-list b { color: var(--md-on-surface); font-variant-numeric: tabular-nums; }
.quantity-list .danger, .quantity-list .danger b { color: var(--el-color-danger); }
.not-in-route { color: var(--md-outline); }
</style>
