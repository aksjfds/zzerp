<script setup lang="ts">
import type { FlowEdge, FlowNode } from '../domain/types'
defineProps<{ node: FlowNode | null; edge: FlowEdge | null }>()
</script>

<template>
  <aside class="property-panel" aria-label="选中元素信息"><span class="panel-label">元素信息</span>
    <template v-if="node">
      <h3>{{ node.type === 'part' ? '配件节点' : '部门节点' }}</h3>
      <p>{{ node.label }}</p>

    </template>
    <template v-else-if="edge"><h3>路线连线</h3></template>
    <div v-else class="selection-empty"><span aria-hidden="true">＋</span><h3>选择画布元素</h3></div>
  </aside>
</template>

<style scoped>
.property-panel { padding: 16px; min-width: 0; border-left: 1px solid var(--erp-border); background: var(--erp-surface-muted); }
h3 { margin: 0 0 12px; font-size: 14px; }
p { overflow-wrap: anywhere; line-height: 1.65; color: var(--erp-text-secondary); font-size: 14px; }
.panel-label { display: block; margin-bottom: 24px; color: var(--erp-text-muted); font-size: 11px; }.selection-empty { padding-top: 32px; text-align: center; }.selection-empty > span { display: grid; place-items: center; width: 40px; height: 40px; margin: 0 auto 16px; border: 1px dashed var(--erp-border-strong); border-radius: 8px; color: var(--erp-text-muted); }.selection-empty p { font-size: 12px; }
</style>
