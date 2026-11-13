<script setup lang="ts">
import type { ProductionDepartment } from '@/features/production-departments'
import type { BomItem } from '../domain/types'

defineProps<{ bomItems: BomItem[]; departments: ProductionDepartment[]; placedBomIds: number[]; loading?: boolean }>()
const emit = defineEmits<{
  dragPart: [part: BomItem]; addPart: [part: BomItem]
  dragDepartment: [department: ProductionDepartment]; addDepartment: [department: ProductionDepartment]
}>()
let pointerType = 'mouse'
function startPointer(event: PointerEvent, drag: () => void) {
  pointerType = event.pointerType
  if (pointerType === 'mouse') drag()
}
function addOnTap(event: MouseEvent, add: () => void) {
  if (pointerType !== 'mouse' || event.detail === 0) add()
}
</script>

<template>
  <aside class="palette">
    <header><strong>流程节点</strong><p>鼠标拖到画布；触屏点击添加，也可聚焦后按 Enter 或空格添加。</p></header>
    <section>
      <h3>配件节点</h3>
      <p>每个 BOM 配件只放置一个路线起点。</p>
      <button v-for="part in bomItems" :key="part.id ?? part.part_no" type="button" class="palette-node part" :disabled="!part.id || placedBomIds.includes(part.id)" @pointerdown="startPointer($event, () => emit('dragPart', part))" @click="addOnTap($event, () => emit('addPart', part))">
        <strong>{{ part.part_name }}</strong><small>{{ part.part_no }}</small>
        <small v-if="part.id && placedBomIds.includes(part.id)">已放置</small>
      </button>
      <p v-if="!bomItems.length">暂无 BOM 配件</p>
    </section>
    <section>
      <h3>部门节点</h3>
      <p>同一部门可放置多个节点，分别安排生产。</p>
      <p v-if="loading">正在加载部门…</p>
      <button v-for="department in departments" :key="department.code" type="button" class="palette-node department" @pointerdown="startPointer($event, () => emit('dragDepartment', department))" @click="addOnTap($event, () => emit('addDepartment', department))">{{ department.name }}</button>
    </section>
  </aside>
</template>

<style scoped>
.palette { padding: 14px; overflow-y: auto; max-height: 850px; border-right: 1px solid var(--erp-border); background: var(--erp-surface-muted); }
section { margin-top: 18px; }
h3 { margin: 0; font-size: 14px; }
p { color: var(--erp-text-secondary); font-size: 12px; line-height: 1.6; }
.palette-node { display: grid; gap: 3px; width: 100%; margin: 8px 0; padding: 12px; border: 1px solid var(--erp-primary); background: var(--erp-surface); color: var(--erp-text); font: inherit; text-align: left; cursor: grab; overflow-wrap: anywhere; }
.part { border-radius: 6px; background: var(--erp-primary-soft); }
.department { border-radius: 24px; text-align: center; }
small { color: var(--erp-text-secondary); font-size: 12px; }
.palette-node:disabled { opacity: .55; cursor: default; }
.palette-node:focus-visible { outline: 2px solid var(--erp-primary); outline-offset: 2px; }
@media (max-width: 900px) { .palette { border-right: 0; border-bottom: 1px solid var(--erp-border); max-height: 350px; } }
</style>
