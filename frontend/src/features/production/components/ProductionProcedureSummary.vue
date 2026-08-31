<script setup lang="ts">
import type { ProductionWorkbenchProcedureSummary } from '../domain/productionWorkbench'

defineProps<{
  items: ProductionWorkbenchProcedureSummary[]
  selected: (item: ProductionWorkbenchProcedureSummary) => boolean
}>()
const emit = defineEmits<{ select: [item?: ProductionWorkbenchProcedureSummary] }>()
</script>

<template>
  <section class="procedure-section">
    <header>
      <h3>加工工艺</h3>
      <ElButton size="small" text @click="emit('select')">全部工单</ElButton>
    </header>
    <div v-if="items.length" class="procedure-list">
      <button
        v-for="item in items"
        :key="`${item.procedure_id}:${item.is_temporary}`"
        type="button"
        :class="{ selected: selected(item) }"
        @click="emit('select', item)"
      >
        <span class="procedure-name">
          <strong>{{ item.procedure_name }}</strong>
          <small>{{ item.is_temporary ? '临时工艺' : '已配置工艺' }}</small>
        </span>
        <span>工单 {{ item.work_order_count }} / 开放 {{ item.open_work_order_count }}</span>
        <span>开单 {{ item.work_order_quantity }}</span>
        <span>加工中 {{ item.processing_quantity }}</span>
        <span>待处理 {{ item.ready_for_result_quantity }}</span>
        <span>质检中 {{ item.pending_qc_quantity }}</span>
        <span>合格 {{ item.qualified_quantity }}</span>
        <span :class="{ exception: item.rework_quantity }">返工 {{ item.rework_quantity }}</span>
      </button>
    </div>
    <ElEmpty v-else description="所选位置暂无工艺记录" :image-size="52" />
  </section>
</template>

<style scoped>
.procedure-section { padding: 14px 16px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); }
header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
h3 { margin: 0; font-size: 15px; }
.procedure-list { display: grid; gap: 7px; margin-top: 10px; }
button { display: grid; grid-template-columns: minmax(130px, 1.4fr) repeat(7, minmax(72px, .7fr)); gap: 8px; align-items: center; width: 100%; padding: 9px 10px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-sm); color: inherit; background: var(--md-surface-container-low); cursor: pointer; text-align: left; }
button:hover, button.selected { border-color: var(--md-primary); background: var(--md-primary-container); }
button span { font-size: 12px; white-space: nowrap; }
.procedure-name { display: grid; gap: 2px; white-space: normal; }
.procedure-name small { color: var(--el-text-color-secondary); }
.exception { color: var(--el-color-danger); }
@media (max-width: 1000px) {
  button { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
</style>
