<script setup lang="ts">
import type { BomItem } from '../domain/types'
import type { ProcedureOption } from '@/api/organization'

defineProps<{ bomItems: BomItem[]; procedures: ProcedureOption[] }>()
const emit = defineEmits<{
  dragAssembly: []
  dragProcedure: [procedure: ProcedureOption]
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
    <h3>工艺</h3>
    <button
      v-for="procedure in procedures"
      :key="procedure.id"
      class="palette-item process"
      type="button"
      @mousedown="emit('dragProcedure', procedure)"
    >＋ {{ procedure.procedure_name }}{{ procedure.procedure_type === 'purchase_receipt' ? '（外购）' : '' }}</button>
    <p v-if="!procedures.length" class="empty">暂无可用工艺</p>
    <h3>流程节点</h3>
    <button class="palette-item assembly" type="button" @mousedown="emit('dragAssembly')">装配</button>
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
.palette-item:disabled { cursor: not-allowed; opacity: .45; }
.empty { margin: 0; color: var(--el-text-color-secondary); font-size: 12px; }
</style>
