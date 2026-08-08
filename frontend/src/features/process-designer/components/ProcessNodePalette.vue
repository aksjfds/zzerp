<script setup lang="ts">
import { computed } from 'vue'
import type { BomItem } from '../domain/types'
import type { ProcedureOption } from '@/api/organization'

const props = defineProps<{ bomItems: BomItem[]; procedures: ProcedureOption[] }>()
type DepartmentGroup = {
  departmentCode: string
  departmentName: string
  procedures: ProcedureOption[]
}

const fixedDepartments = [
  { departmentCode: 'qc', departmentName: 'QC部门' },
  { departmentCode: 'assembly', departmentName: '装配部' },
  { departmentCode: 'finished', departmentName: '成品部' },
]
const departmentOrder = [
  'stamp',
  'cnc',
  'polish',
  'outsource',
  'purchasing',
  'qc',
  'assembly',
  'finished',
]

const departmentGroups = computed<DepartmentGroup[]>(() => {
  const groups = new Map<string, DepartmentGroup>()
  props.procedures.forEach((procedure) => {
    const group = groups.get(procedure.department_code) ?? {
      departmentCode: procedure.department_code,
      departmentName: procedure.department_name,
      procedures: [],
    }
    group.procedures.push(procedure)
    groups.set(procedure.department_code, group)
  })
  fixedDepartments.forEach((department) => {
    if (!groups.has(department.departmentCode)) {
      groups.set(department.departmentCode, { ...department, procedures: [] })
    }
  })
  return [...groups.values()].sort((left, right) => {
    const leftIndex = departmentOrder.indexOf(left.departmentCode)
    const rightIndex = departmentOrder.indexOf(right.departmentCode)
    return (leftIndex < 0 ? departmentOrder.length : leftIndex)
      - (rightIndex < 0 ? departmentOrder.length : rightIndex)
  })
})
const emit = defineEmits<{
  dragAssembly: []
  dragQc: []
  dragShipping: []
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
    <template v-for="group in departmentGroups" :key="group.departmentCode">
      <h3>{{ group.departmentName }}</h3>
      <button
        v-for="procedure in group.procedures"
        :key="procedure.id"
        class="palette-item"
        :class="procedure.procedure_type === 'purchase_receipt' ? 'purchase' : 'process'"
        type="button"
        @mousedown="emit('dragProcedure', procedure)"
      >＋ {{ procedure.procedure_name }}</button>
      <button v-if="group.departmentCode === 'qc'" class="palette-item qc" type="button" @mousedown="emit('dragQc')">QC</button>
      <button v-if="group.departmentCode === 'assembly'" class="palette-item assembly" type="button" @mousedown="emit('dragAssembly')">装配</button>
      <button v-if="group.departmentCode === 'finished'" class="palette-item shipping" type="button" @mousedown="emit('dragShipping')">发货</button>
    </template>
  </aside>
</template>

<style scoped>
.palette { box-sizing: border-box; height: 560px; min-height: 0; padding: 16px; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; border-right: 1px solid var(--md-outline-variant); background: var(--md-surface-container-low); }
h3 { margin: 0 0 10px; font-size: 14px; }
.palette h3:not(:first-child) { margin-top: 22px; }
.palette-item { display: flex; flex-direction: column; width: 100%; min-height: 48px; margin-bottom: 8px; padding: 9px 11px; border: 1px solid; border-radius: var(--erp-radius); background: var(--md-surface-container-lowest); color: var(--md-on-surface); text-align: left; cursor: grab; }
.palette-item span { margin-top: 3px; color: var(--md-on-surface-variant); font-size: 11px; }
.palette-item.part { border-color: var(--md-primary); background: var(--md-primary-container); }
.palette-item.process { border-color: var(--erp-success); background: var(--md-success-container); }
.palette-item.purchase { border-color: var(--erp-warning); background: var(--md-warning-container); }
.palette-item.qc { border-color: var(--md-tertiary); background: var(--md-tertiary-container); }
.palette-item.shipping { border-color: var(--md-secondary); background: var(--md-secondary-container); }
.palette-item.assembly { border-color: var(--erp-warning); background: var(--md-warning-container); }
.palette-item:disabled { cursor: not-allowed; opacity: .45; }
@media (max-width: 900px) {
  .palette { max-height: 240px; overflow-y: auto; border-right: 0; border-bottom: 1px solid var(--md-outline-variant); }
}
</style>
