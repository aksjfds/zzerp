<script setup lang="ts">
import type {
  AssemblyWorkbenchContinuationSource,
  ProductionWorkbenchPosition,
  StandardWorkbenchSource,
} from '../domain/productionWorkbench'

defineProps<{
  position: ProductionWorkbenchPosition
  selectedStandardSource?: StandardWorkbenchSource
  selectedContinuationSource?: AssemblyWorkbenchContinuationSource
}>()
const emit = defineEmits<{
  createStandard: []
  createInitialAssembly: []
  createContinuation: []
  selectStandardSource: [source: StandardWorkbenchSource]
  selectContinuationSource: [source: AssemblyWorkbenchContinuationSource]
}>()

function sourceLabel(index: number, available: number, arrivedAt: string | null) {
  return `来源 ${index + 1} · 可开工 ${available} · 到达 ${arrivedAt || '—'}`
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
      <div class="primary-actions">
        <template v-if="position.position_type === 'assembly'">
          <ElButton
            type="primary"
            :disabled="!position.can_create_initial_work_order"
            @click="emit('createInitialAssembly')"
          >首次{{ position.workshop_name }}开单</ElButton>
          <ElButton
            type="primary"
            plain
            :disabled="!selectedContinuationSource?.can_create_work_order"
            @click="emit('createContinuation')"
          >在制品后续开单</ElButton>
        </template>
        <ElButton
          v-else
          type="primary"
          :disabled="!selectedStandardSource?.can_create_work_order"
          @click="emit('createStandard')"
        >开{{ position.workshop_name }}工单</ElButton>
      </div>
    </header>

    <template v-if="position.position_type === 'assembly'">
      <dl class="overview-grid">
        <div><dt>当前车间</dt><dd>{{ position.workshop_name }}</dd></div>
        <div><dt>综合可开工</dt><dd>{{ position.capacity_quantity }}</dd></div>
        <div><dt>首次多路可开工</dt><dd>{{ position.initial_capacity_quantity }}</dd></div>
        <div><dt>在制品后续可开工</dt><dd>{{ position.continuation_capacity_quantity }}</dd></div>
        <div><dt>输入物料</dt><dd>{{ position.input_material_count }} 项</dd></div>
        <div><dt>工艺配置</dt><dd>{{ position.procedure_configuration_confirmed ? '已确认' : '未确认' }}</dd></div>
      </dl>

      <section class="material-section">
        <header><h3>首次多路输入</h3><span>{{ position.input_materials_complete ? '物料已到齐' : '物料未到齐' }}</span></header>
        <div class="material-list">
          <article v-for="material in position.input_materials" :key="material.material_key">
            <div>
              <strong>{{ material.item_code }} · {{ material.item_name }}</strong>
              <span>每件用量 {{ material.unit_quantity }}</span>
            </div>
            <dl>
              <div><dt>在位</dt><dd>{{ material.on_hand_quantity }}</dd></div>
              <div><dt>占用</dt><dd>{{ material.reserved_quantity }}</dd></div>
              <div><dt>可用</dt><dd>{{ material.available_quantity }}</dd></div>
              <div><dt>已投入开放工单</dt><dd>{{ material.allocated_quantity }}</dd></div>
            </dl>
            <p v-if="material.sources.length > 1">{{ material.sources.length }} 个可分配来源</p>
          </article>
        </div>
      </section>

      <div v-if="position.continuation_sources.length" class="source-row">
        <label>节点在制品来源</label>
        <ElSelect
          :model-value="selectedContinuationSource?.repository_id"
          placeholder="选择后续工艺来源"
          @update:model-value="value => {
            const source = position.continuation_sources.find(item => item.repository_id === value)
            if (source) emit('selectContinuationSource', source)
          }"
        >
          <ElOption
            v-for="(source, index) in position.continuation_sources"
            :key="source.repository_id"
            :label="sourceLabel(index, source.available_quantity, source.arrived_at)"
            :value="source.repository_id"
          />
        </ElSelect>
        <span v-if="!selectedContinuationSource && position.continuation_sources.length > 1">存在多个来源，请先选择</span>
      </div>
    </template>

    <template v-else>
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
          :model-value="selectedStandardSource?.repository_id"
          placeholder="选择来源"
          @update:model-value="value => {
            const source = position.sources.find(item => item.repository_id === value)
            if (source) emit('selectStandardSource', source)
          }"
        >
          <ElOption
            v-for="(source, index) in position.sources"
            :key="source.repository_id"
            :label="sourceLabel(index, source.available_quantity, source.arrived_at)"
            :value="source.repository_id"
          />
        </ElSelect>
        <span v-if="!selectedStandardSource && position.sources.length > 1">存在多个来源，请先选择</span>
      </div>
    </template>
  </section>
</template>

<style scoped>
.position-overview { padding: 18px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); }
.position-overview > header { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; }
h2, h3, p { margin: 0; }
h2 { margin: 4px 0; font-size: 19px; }
h3 { font-size: 14px; }
p, .material-section header span { color: var(--el-text-color-secondary); font-size: 12px; }
.primary-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.primary-actions :deep(.el-button) { margin: 0; }
.overview-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 16px 0 0; }
.overview-grid > div { padding: 10px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-low); }
dt { color: var(--el-text-color-secondary); font-size: 12px; }
dd { margin: 5px 0 0; font-weight: 650; overflow-wrap: anywhere; }
.material-section { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--erp-border); }
.material-section > header { display: flex; justify-content: space-between; gap: 10px; }
.material-list { display: grid; gap: 8px; margin-top: 9px; }
.material-list article { padding: 10px 12px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-low); }
.material-list article > div { display: flex; justify-content: space-between; gap: 12px; }
.material-list article span { color: var(--el-text-color-secondary); font-size: 12px; }
.material-list dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px; margin: 9px 0 0; }
.material-list dl div { padding: 7px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-lowest); }
.source-row { display: grid; grid-template-columns: auto minmax(260px, 1fr) auto; gap: 10px; align-items: center; margin-top: 14px; }
.source-row label, .source-row span { color: var(--el-text-color-secondary); font-size: 12px; }
@media (max-width: 760px) {
  .position-overview > header { flex-direction: column; }
  .primary-actions { justify-content: flex-start; }
  .overview-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .material-list dl { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .source-row { grid-template-columns: 1fr; }
}
</style>
