<script setup lang="ts">
defineProps<{ showEdgeWidth?: boolean }>()
const emit = defineEmits<{
  fontSize: [delta: number]
  nodeSize: [delta: number]
  edgeWidth: [delta: number]
}>()
</script>

<template>
  <div class="flow-display-controls" role="group" aria-label="流程图显示设置">
    <div class="display-control-group">
      <span>字体</span>
      <button type="button" aria-label="缩小字体" title="缩小字体" @click="emit('fontSize', -1)">−</button>
      <button type="button" aria-label="放大字体" title="放大字体" @click="emit('fontSize', 1)">＋</button>
    </div>
    <div class="display-control-group">
      <span>节点</span>
      <button type="button" aria-label="缩小节点" title="缩小节点" @click="emit('nodeSize', -0.1)">−</button>
      <button type="button" aria-label="放大节点" title="放大节点" @click="emit('nodeSize', 0.1)">＋</button>
    </div>
    <div v-if="showEdgeWidth" class="display-control-group">
      <span>连线</span>
      <button type="button" aria-label="变细连线" title="变细连线" @click="emit('edgeWidth', -1)">−</button>
      <button type="button" aria-label="加粗连线" title="加粗连线" @click="emit('edgeWidth', 1)">＋</button>
    </div>
  </div>
</template>

<style scoped>
.flow-display-controls { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; padding: 8px 10px; border-bottom: 1px solid var(--erp-border); background: var(--erp-surface-muted); }
.display-control-group { display: flex; align-items: center; gap: 4px; color: var(--erp-text-secondary); font-size: 12px; }
.display-control-group span { margin-inline: 4px; }
button { display: grid; width: 32px; height: 32px; place-items: center; padding: 0; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-sm); color: var(--erp-text); background: var(--erp-surface); cursor: pointer; font-size: 16px; }
button:hover { border-color: var(--erp-primary); color: var(--erp-primary); background: var(--erp-primary-soft); }
@media (max-width: 600px) { .flow-display-controls { justify-content: flex-start; } }
@media (pointer: coarse) { button { width: 44px; height: 44px; } }
</style>
