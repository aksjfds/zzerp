<script setup lang="ts">
import type { BomItem } from '../domain/types'

defineProps<{ bomItems: BomItem[] }>()
const emit = defineEmits<{
  addAssembly: []
  addProcess: []
  addQc: []
  dragPart: [item: BomItem]
}>()
</script>

<template>
  <aside class="palette">
    <h3>BOM 配件</h3>
    <button
      v-for="item in bomItems"
      :key="item.id ?? item.part_no"
      class="palette-item part"
      type="button"
      :disabled="!item.id"
      @mousedown="emit('dragPart', item)"
    >
      <strong>{{ item.part_name }}</strong>
      <span>{{ item.part_no }}</span>
    </button>
    <h3>流程节点</h3>
    <button class="palette-item process" type="button" @click="emit('addProcess')">＋ 工序节点</button>
    <button class="palette-item assembly" type="button" @click="emit('addAssembly')">＋ 装配节点</button>
    <button class="palette-item qc" type="button" @click="emit('addQc')">＋ QC 节点</button>
  </aside>
</template>

<style scoped>
.palette { padding: 16px; border-right: 1px solid var(--erp-border); background: #f8fafc; }
h3 { margin: 0 0 10px; font-size: 14px; }
.palette h3:not(:first-child) { margin-top: 22px; }
.palette-item { display: flex; flex-direction: column; width: 100%; margin-bottom: 8px; padding: 9px 11px; border: 1px solid; border-radius: 6px; background: #fff; text-align: left; cursor: grab; }
.palette-item span { margin-top: 3px; color: #64748b; font-size: 11px; }
.palette-item.part { border-color: #409eff; }
.palette-item.process { border-color: #67c23a; }
.palette-item.assembly { border-color: #e6a23c; }
.palette-item.qc { border-color: #f56c6c; }
.palette-item:disabled { cursor: not-allowed; opacity: .45; }
</style>
