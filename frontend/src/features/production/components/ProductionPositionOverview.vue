<script setup lang="ts">
import type {
  StandardWorkbenchPosition,
  StandardWorkbenchSource,
} from '../domain/productionWorkbench'

defineProps<{
  position: StandardWorkbenchPosition
  selectedSource?: StandardWorkbenchSource
}>()
const emit = defineEmits<{
  createWorkOrder: []
  selectSource: [source: StandardWorkbenchSource]
}>()

function sourceLabel(source: StandardWorkbenchSource, index: number) {
  return `来源 ${index + 1} · 在位 ${source.on_hand_quantity} · 可开工 ${source.available_quantity} · 到达 ${source.arrived_at || '—'}`
}
</script>

<template>
  <section class="position-overview">
    <header>
      <div>
        <p>{{ position.customer_order_no }} · {{ position.customer_name }}</p>
        <h2>{{ position.item_code }} · {{ position.item_name }}</h2>
        <p>{{ position.factory_code }} · {{ position.product_name }} · V{{ position.product_version }}</p>
      </div>
      <ElButton type="primary" :disabled="!selectedSource?.can_create_work_order" @click="emit('createWorkOrder')">
        开工单
      </ElButton>
    </header>
    <dl class="overview-grid">
      <div><dt>当前车间</dt><dd>{{ position.workshop_name }}</dd></div>
      <div><dt>来源完成状态</dt><dd>{{ position.source_node_label }}</dd></div>
      <div><dt>在位数量</dt><dd>{{ position.on_hand_quantity }}</dd></div>
      <div><dt>占用数量</dt><dd>{{ position.reserved_quantity }}</dd></div>
      <div><dt>可开工数量</dt><dd>{{ position.available_quantity }}</dd></div>
      <div><dt>到达时间</dt><dd>{{ position.arrived_at || '—' }}</dd></div>
    </dl>
    <div class="source-row">
      <label>开单物料来源</label>
      <ElSelect
        :model-value="selectedSource?.repository_id"
        placeholder="选择来源"
        @update:model-value="value => {
          const source = position.sources.find(item => item.repository_id === value)
          if (source) emit('selectSource', source)
        }"
      >
        <ElOption
          v-for="(source, index) in position.sources"
          :key="source.repository_id"
          :label="sourceLabel(source, index)"
          :value="source.repository_id"
        />
      </ElSelect>
      <span v-if="selectedSource">
        {{ selectedSource.procedure_configuration_confirmed ? '工艺配置已确认' : '工艺配置未确认' }}
      </span>
      <span v-else-if="position.sources.length > 1">存在多个来源，请先选择</span>
    </div>
  </section>
</template>

<style scoped>
.position-overview { padding: 18px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); }
header { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; }
h2, p { margin: 0; }
h2 { margin: 4px 0; font-size: 19px; }
p { color: var(--el-text-color-secondary); font-size: 13px; }
.overview-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 16px 0 0; }
.overview-grid div { padding: 10px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-low); }
dt { color: var(--el-text-color-secondary); font-size: 12px; }
dd { margin: 5px 0 0; font-weight: 650; overflow-wrap: anywhere; }
.source-row { display: grid; grid-template-columns: auto minmax(260px, 1fr) auto; gap: 10px; align-items: center; margin-top: 14px; }
.source-row label, .source-row span { color: var(--el-text-color-secondary); font-size: 12px; }
@media (max-width: 700px) {
  .overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .source-row { grid-template-columns: 1fr; }
}
</style>
