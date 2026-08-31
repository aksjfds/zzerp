<script setup lang="ts">
import type { ProductionWorkbenchPosition } from '../domain/productionWorkbench'

defineProps<{
  items: ProductionWorkbenchPosition[]
  loading: boolean
  selectedKey?: string
}>()
const emit = defineEmits<{ select: [item: ProductionWorkbenchPosition] }>()
</script>

<template>
  <div v-loading="loading" class="position-list">
    <article
      v-for="item in items"
      :key="item.position_key"
      class="position-item"
      :class="{ selected: item.position_key === selectedKey }"
      tabindex="0"
      @click="emit('select', item)"
      @keydown.enter="emit('select', item)"
    >
      <header>
        <strong>{{ item.item_code }} · {{ item.item_name }}</strong>
        <span>{{ item.workshop_name }}</span>
      </header>
      <p>{{ item.factory_code }} · {{ item.product_name }}</p>
      <p>订单 {{ item.customer_order_no }} · {{ item.customer_name }}</p>
      <dl v-if="item.position_type === 'assembly'">
        <div><dt>可开工</dt><dd>{{ item.capacity_quantity }}</dd></div>
        <div><dt>首次</dt><dd>{{ item.initial_capacity_quantity }}</dd></div>
        <div><dt>在制品</dt><dd>{{ item.continuation_capacity_quantity }}</dd></div>
        <div><dt>输入物料</dt><dd>{{ item.input_material_count }}</dd></div>
      </dl>
      <dl v-else>
        <div><dt>在位</dt><dd>{{ item.on_hand_quantity }}</dd></div>
        <div><dt>占用</dt><dd>{{ item.reserved_quantity }}</dd></div>
        <div><dt>可开工</dt><dd>{{ item.available_quantity }}</dd></div>
        <div><dt>来源</dt><dd>{{ item.source_count }}</dd></div>
      </dl>
      <div class="activity-counts">
        <span v-if="item.activity.processing_work_order_count" class="processing">加工中 {{ item.activity.processing_work_order_count }}</span>
        <span v-if="item.activity.ready_for_result_work_order_count" class="ready">待处理 {{ item.activity.ready_for_result_work_order_count }}</span>
        <span v-if="item.activity.pending_qc_work_order_count" class="qc">质检中 {{ item.activity.pending_qc_work_order_count }}</span>
        <span v-if="item.activity.rework_work_order_count" class="rework">返工中 {{ item.activity.rework_work_order_count }}</span>
        <span v-if="!item.activity.open_work_order_count" class="quiet">暂无开放工单</span>
      </div>
      <footer>
        到达：{{ item.arrived_at || '—' }}
        <span v-if="item.last_activity_at"> · 最近加工：{{ item.last_activity_at }}</span>
      </footer>
    </article>
    <ElEmpty v-if="!loading && !items.length" description="装配部暂无在位物料" :image-size="72" />
  </div>
</template>

<style scoped>
.position-list { display: grid; grid-auto-rows: max-content; align-content: start; gap: 10px; min-height: 150px; padding-right: 3px; }
.position-item { padding: 13px 14px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius); background: var(--md-surface-container-low); cursor: pointer; box-shadow: var(--erp-shadow-sm); transition: border-color .16s, background-color .16s, box-shadow .16s; }
.position-item:hover, .position-item:focus-visible { border-color: var(--erp-primary); outline: none; }
.position-item.selected { border-color: var(--md-primary); background: var(--md-primary-container); box-shadow: 0 0 0 1px var(--md-primary); }
header { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
header strong { min-width: 0; line-height: 1.45; overflow-wrap: anywhere; }
header span, p, footer { color: var(--el-text-color-secondary); font-size: 12px; }
p { margin: 6px 0 0; }
dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; margin: 11px 0 0; }
dl div { padding: 7px 6px; border-radius: var(--erp-radius-sm); background: var(--md-surface-container-lowest); text-align: center; }
dt { color: var(--el-text-color-secondary); font-size: 11px; }
dd { margin: 3px 0 0; font-weight: 700; }
.activity-counts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; font-size: 11px; }
.activity-counts span { padding: 3px 7px; border-radius: 999px; background: var(--md-surface-container-lowest); }
.processing { color: #8a4b08; }
.ready { color: #176b3a; }
.qc { color: #6b21a8; }
.rework { color: #b42318; }
.quiet { color: var(--el-text-color-secondary); }
footer { margin-top: 9px; }
</style>
