<script setup lang="ts">
import type { SubstepCard } from '../domain/types'

const props = defineProps<{
  items: SubstepCard[]
  loading: boolean
  procedureName?: string
  selectedKey?: string | null
}>()
const emit = defineEmits<{
  select: [item: SubstepCard]
  createWorkOrder: [item: SubstepCard]
}>()

function cardName(item: SubstepCard) {
  if (item.substep_id === null) {
    return item.substep_name || `未${props.procedureName || '加工'}`
  }
  return item.substep_name || '未命名细分'
}

</script>

<template>
  <div v-loading="loading" class="substep-cards">
    <article
      v-for="item in items"
      :key="item.card_key"
      class="substep-card"
      :class="{ selected: item.card_key === selectedKey }"
      tabindex="0"
      @click="emit('select', item)"
      @keydown.enter="emit('select', item)"
    >
      <div class="substep-heading">
        <strong>{{ cardName(item) }}</strong>
        <ElTag v-if="item.substep_id === null" type="info" size="small">待加工</ElTag>
        <ElTag v-else-if="item.processing_quantity > 0" type="warning" size="small">进行中</ElTag>
        <ElTag v-else-if="item.pending_qc_quantity > 0" type="warning" size="small">质检中</ElTag>
        <ElTag v-else-if="item.completed_quantity > 0" type="success" size="small">已完</ElTag>
        <ElTag v-else type="info" size="small">暂无数量</ElTag>
      </div>

      <dl v-if="item.substep_id === null" class="substep-metrics initial-metrics">
        <div><dt>未加工</dt><dd>{{ item.available_quantity }}</dd></div>
      </dl>
      <dl v-else class="substep-metrics">
        <div><dt>进行中</dt><dd>{{ item.processing_quantity }}</dd></div>
        <div><dt>质检中</dt><dd>{{ item.pending_qc_quantity }}</dd></div>
        <div><dt>已完</dt><dd>{{ item.completed_quantity }}</dd></div>
      </dl>

      <div class="substep-actions">
        <ElButton
          type="primary"
          plain
          size="small"
          :disabled="!item.can_create_work_order || item.available_quantity < 1"
          @click.stop="emit('createWorkOrder', item)"
        >开工单</ElButton>
      </div>
    </article>
    <ElEmpty v-if="!loading && !items.length" description="所选配件暂无细分记录" :image-size="64" />
  </div>
</template>

<style scoped>
.substep-cards { display: grid; grid-auto-flow: column; grid-auto-columns: minmax(220px, 280px); gap: 12px; min-height: 160px; overflow-x: auto; padding-bottom: 4px; }
.substep-card { padding: 14px; border: 1px solid var(--erp-border); border-radius: 8px; background: #f8fafc; cursor: pointer; transition: border-color .15s, box-shadow .15s; }
.substep-card:hover, .substep-card:focus-visible { border-color: var(--erp-primary); outline: none; }
.substep-card.selected { border-color: var(--erp-primary); box-shadow: 0 0 0 2px color-mix(in srgb, var(--erp-primary) 14%, transparent); }
.substep-heading { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.substep-heading strong { min-width: 0; overflow-wrap: anywhere; }
.substep-metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 13px 0 0; }
.substep-metrics div { padding: 9px; border-radius: 6px; background: #fff; }
.substep-metrics dt { color: var(--el-text-color-secondary); font-size: 12px; }
.substep-metrics dd { margin: 4px 0 0; font-size: 17px; font-weight: 700; }
.initial-metrics { grid-template-columns: 1fr; }
.substep-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; margin-top: 12px; }
.substep-actions :deep(.el-button) { width: 100%; margin: 0; }
</style>
