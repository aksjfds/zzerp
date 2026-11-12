<script setup lang="ts">
import type { FlowEdge, FlowNode } from '../domain/types'
defineProps<{ node: FlowNode | null; edge: FlowEdge | null }>()
</script>

<template>
  <aside class="property-panel">
    <template v-if="node">
      <h3>{{ node.type === 'part' ? '配件节点' : '部门节点' }}</h3>
      <p>{{ node.label }}</p>
      <p>{{ node.type === 'part' ? '引用 BOM 配件，作为路线起点。名称随配件资料显示。' : '引用生产部门，同一部门可放置多个节点。' }}</p>
    </template>
    <template v-else-if="edge"><h3>路线连线</h3><p>配件沿连线经过部门节点，创建计划时据此安排部门工单。</p></template>
  </aside>
</template>

<style scoped>
.property-panel { padding: 16px; min-width: 0; border-left: 1px solid var(--erp-border); background: var(--erp-surface-muted); }
h3 { margin: 0 0 12px; font-size: 14px; }
p { overflow-wrap: anywhere; line-height: 1.6; color: var(--erp-text-secondary); font-size: 13px; }
</style>
