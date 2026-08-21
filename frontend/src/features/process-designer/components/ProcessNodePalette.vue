<script setup lang="ts">
import { computed } from 'vue'
import type { BomItem } from '../domain/types'
import type { WorkshopRouteOption } from '@/api/organization'

const props = defineProps<{
  bomItems: BomItem[]
  workshops: WorkshopRouteOption[]
  placedBomIds: number[]
}>()
type DepartmentGroup = {
  departmentCode: string
  departmentName: string
  workshops: WorkshopRouteOption[]
}
const fixedDepartments = [
  { departmentCode: 'qc', departmentName: 'QC部门' },
  { departmentCode: 'finished', departmentName: '成品部' },
]
const departmentOrder = [
  'stamp', 'cnc', 'polish', 'outsource', 'purchasing', 'qc', 'assembly', 'finished',
]
const departmentGroups = computed<DepartmentGroup[]>(() => {
  const groups = new Map<string, DepartmentGroup>()
  props.workshops.forEach((workshop) => {
    const group = groups.get(workshop.department_code) ?? {
      departmentCode: workshop.department_code,
      departmentName: workshop.department_name,
      workshops: [],
    }
    group.workshops.push(workshop)
    groups.set(workshop.department_code, group)
  })
  fixedDepartments.forEach((department) => {
    if (!groups.has(department.departmentCode)) {
      groups.set(department.departmentCode, { ...department, workshops: [] })
    }
  })
  return [...groups.values()].sort((left, right) => {
    const a = departmentOrder.indexOf(left.departmentCode)
    const b = departmentOrder.indexOf(right.departmentCode)
    return (a < 0 ? departmentOrder.length : a) - (b < 0 ? departmentOrder.length : b)
  })
})
function fixedNodeCount(code: string) {
  return ['qc', 'finished'].includes(code) ? 1 : 0
}
function workshopColorClass(workshop: WorkshopRouteOption) {
  if (workshop.department_code === 'outsource') return 'outsource'
  if (workshop.department_code === 'purchasing') return 'purchase'
  if (workshop.department_code === 'assembly') return 'assembly'
  return 'process'
}
const emit = defineEmits<{
  dragQc: []
  dragShipping: []
  dragWorkshop: [workshop: WorkshopRouteOption]
  dragPart: [item: BomItem]
}>()
</script>

<template>
  <aside class="palette">
    <header class="palette-heading">
      <strong>流程节点</strong>
      <span>按住条目并拖到右侧画布</span>
    </header>

    <section class="palette-group part-group">
      <div class="group-heading">
        <div>
          <span class="group-mark part-mark" />
          <h3>BOM 配件</h3>
        </div>
        <span class="group-count">{{ bomItems.length }}</span>
      </div>
      <p class="group-hint">每个 BOM 配件在流程图中只能放置一次。</p>
      <div class="group-items">
        <button
          v-for="item in bomItems"
          :key="item.id ?? item.part_no"
          class="palette-item part"
          type="button"
          :disabled="!item.id || placedBomIds.includes(item.id)"
          :title="!item.id ? '请先保存 BOM 配件' : placedBomIds.includes(item.id) ? '该配件已放入流程图' : `拖动配件“${item.part_name}”到画布`"
          @mousedown="emit('dragPart', item)"
        >
          <span class="drag-handle" aria-hidden="true">⠿</span>
          <span class="item-content">
            <strong>{{ item.part_name }}</strong>
            <small>{{ item.part_no }}</small>
          </span>
          <span class="item-kind">配件</span>
        </button>
        <p v-if="!bomItems.length" class="empty-hint">暂无 BOM 配件</p>
      </div>
    </section>

    <section
      v-for="group in departmentGroups"
      :key="group.departmentCode"
      class="palette-group"
      :class="`department-${group.departmentCode}`"
    >
      <div class="group-heading">
        <div>
          <span class="group-mark" />
          <h3>{{ group.departmentName }}</h3>
        </div>
        <span class="group-count">{{ group.workshops.length + fixedNodeCount(group.departmentCode) }}</span>
      </div>
      <div class="group-items">
        <button
          v-for="workshop in group.workshops"
          :key="workshop.id"
          class="palette-item"
          :class="workshopColorClass(workshop)"
          type="button"
          :title="`拖动“${workshop.workshop_name}”到画布`"
          @mousedown="emit('dragWorkshop', workshop)"
        >
          <span class="drag-handle" aria-hidden="true">⠿</span>
          <span class="item-content"><strong>{{ workshop.workshop_name }}</strong></span>
          <span class="item-kind">{{ workshop.department_code === 'assembly' ? '多路' : '车间' }}</span>
        </button>
        <button v-if="group.departmentCode === 'qc'" class="palette-item qc" type="button" title="拖动 QC 到画布" @mousedown="emit('dragQc')">
          <span class="drag-handle" aria-hidden="true">⠿</span><span class="item-content"><strong>QC</strong></span><span class="item-kind">QC</span>
        </button>
        <button v-if="group.departmentCode === 'finished'" class="palette-item shipping" type="button" title="拖动发货节点到画布" @mousedown="emit('dragShipping')">
          <span class="drag-handle" aria-hidden="true">⠿</span><span class="item-content"><strong>发货</strong></span><span class="item-kind">发货</span>
        </button>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.palette { box-sizing: border-box; height: clamp(620px, 72vh, 820px); min-height: 0; padding: 12px; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; border-right: 1px solid var(--md-outline-variant); background: var(--md-surface-container-low); }
.palette-heading { margin: 0 2px 12px; }
.palette-heading strong { display: block; color: var(--md-on-surface); font-size: 15px; }
.palette-heading span { display: block; margin-top: 3px; color: var(--md-on-surface-variant); font-size: 11px; line-height: 1.4; }
.palette-group { margin-bottom: 12px; overflow: hidden; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius); background: var(--md-surface-container-lowest); }
.group-heading { display: flex; align-items: center; justify-content: space-between; min-height: 34px; padding: 0 9px; border-bottom: 1px solid var(--md-outline-variant); background: var(--md-surface-container); }
.group-heading > div { display: flex; min-width: 0; align-items: center; gap: 7px; }
.group-heading h3 { overflow: hidden; margin: 0; color: var(--md-on-surface); font-size: 12px; font-weight: 700; text-overflow: ellipsis; white-space: nowrap; }
.group-mark { width: 4px; height: 14px; flex: 0 0 auto; border-radius: 999px; background: var(--flow-production); }
.part-mark { background: var(--md-primary); }
.department-outsource .group-mark { background: var(--flow-outsource); }
.department-purchasing .group-mark { background: var(--flow-purchasing); }
.department-qc .group-mark { background: var(--flow-qc); }
.department-assembly .group-mark { background: var(--flow-assembly); }
.department-finished .group-mark { background: var(--flow-finished); }
.group-count { min-width: 20px; padding: 1px 5px; border-radius: 999px; background: var(--md-surface-container-high); color: var(--md-on-surface-variant); font-size: 10px; line-height: 16px; text-align: center; }
.group-items { display: grid; gap: 6px; padding: 7px; }
.group-hint { margin: 0; padding: 7px 9px 0; color: var(--md-on-surface-variant); font-size: 10px; line-height: 1.4; }
.palette-item { display: flex; width: 100%; min-height: 40px; align-items: center; gap: 7px; padding: 6px 7px; border: 1px solid; border-radius: calc(var(--erp-radius) - 2px); background: var(--md-surface-container-lowest); color: var(--md-on-surface); text-align: left; cursor: grab; transition: transform .12s ease, box-shadow .12s ease; }
.palette-item:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 2px 6px rgb(0 0 0 / 10%); }
.palette-item:active:not(:disabled) { cursor: grabbing; transform: translateY(0); box-shadow: none; }
.drag-handle { flex: 0 0 auto; color: var(--md-on-surface-variant); font-size: 15px; line-height: 1; opacity: .65; }
.item-content { display: flex; min-width: 0; flex: 1; flex-direction: column; }
.item-content strong { overflow: hidden; font-size: 12px; font-weight: 600; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.item-content small { overflow: hidden; margin-top: 1px; color: var(--md-on-surface-variant); font-size: 10px; line-height: 1.25; text-overflow: ellipsis; white-space: nowrap; }
.item-kind { flex: 0 0 auto; padding: 2px 5px; border-radius: 4px; background: rgb(255 255 255 / 58%); color: var(--md-on-surface-variant); font-size: 9px; line-height: 1.4; }
.empty-hint { margin: 6px; color: var(--md-on-surface-variant); font-size: 11px; text-align: center; }
.palette-item.part { border-color: var(--md-primary); background: var(--md-primary-container); }
.palette-item.process { border-color: var(--flow-production); background: var(--flow-production-container); }
.palette-item.outsource { border-color: var(--flow-outsource); background: var(--flow-outsource-container); }
.palette-item.purchase { border-color: var(--flow-purchasing); background: var(--flow-purchasing-container); }
.palette-item.qc { border-color: var(--flow-qc); background: var(--flow-qc-container); }
.palette-item.shipping { border-color: var(--flow-finished); background: var(--flow-finished-container); }
.palette-item.assembly { border-color: var(--flow-assembly); background: var(--flow-assembly-container); }
.palette-item:disabled { cursor: not-allowed; opacity: .45; }
@media (max-width: 900px) {
  .palette { height: auto; max-height: 280px; overflow-y: auto; border-right: 0; border-bottom: 1px solid var(--md-outline-variant); }
}
</style>
