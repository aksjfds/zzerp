<script setup lang="ts">
import { computed } from 'vue'
import type { DepartmentProductionProgressItem } from '../domain/productionProgress'
import {
  buildProductionTaskRows,
  displayWorkshopName,
  productionTaskSpan,
  type ProductionTaskTreeRow,
} from '../domain/productionTaskTree'

const props = defineProps<{
  items: DepartmentProductionProgressItem[]
  departmentCode: string
  loading: boolean
}>()
const emit = defineEmits<{
  select: [item: DepartmentProductionProgressItem]
}>()

const rows = computed(() => buildProductionTaskRows(props.items, props.departmentCode))

function spanMethod({ row, column }: {
  row: ProductionTaskTreeRow
  column: { property?: string }
}) {
  return productionTaskSpan(props.departmentCode, row, column.property)
}
</script>

<template>
  <ElTable
    v-table-column-widths="'production.department-tasks'"
    v-loading="loading"
    :data="rows"
    row-key="row_key"
    border
    stripe
    table-layout="auto"
    empty-text="暂无生产任务"
    :span-method="spanMethod"
  >
    <ElTableColumn prop="part_name" label="配件/装配体" min-width="210">
      <template #default="{ row }">
        <span v-if="row.is_material" class="tree-name material-name">
          <span class="directory-icon file-icon" aria-hidden="true" />
          <span>{{ row.part_name }}</span>
        </span>
        <ElLink
          v-else
          class="tree-name"
          type="primary"
          :underline="false"
          @click="emit('select', row)"
        >
          <span v-if="row.has_materials" class="directory-icon folder-icon" aria-hidden="true" />
          <span>{{ row.part_name }}</span>
        </ElLink>
      </template>
    </ElTableColumn>
    <ElTableColumn prop="part_no" label="物料编号" min-width="150" />
    <ElTableColumn prop="processing_workshop" label="加工工艺" min-width="160">
      <template #default="{ row }">{{ displayWorkshopName(row.processing_workshop) }}</template>
    </ElTableColumn>
    <ElTableColumn prop="task_quantity" label="任务数" min-width="90" align="right" />
    <ElTableColumn label="到货数" min-width="100" align="right">
      <template #default="{ row }">{{ row.has_materials ? '—' : row.arrived_quantity }}</template>
    </ElTableColumn>
    <ElTableColumn prop="completed_quantity" label="完成数" min-width="110" align="right">
      <template #default="{ row }">
        <span v-if="!row.is_material" class="completed">{{ row.completed_quantity }}</span>
        <span v-else>—</span>
      </template>
    </ElTableColumn>
    <ElTableColumn prop="remark" label="备注" min-width="220" show-overflow-tooltip>
      <template #default="{ row }">{{ row.remark || '—' }}</template>
    </ElTableColumn>
  </ElTable>
</template>

<style scoped>
.completed { color: #16a34a; font-weight: 700; }
.tree-name { display: inline-flex; align-items: center; gap: 7px; }
.directory-icon { position: relative; display: inline-block; flex: 0 0 auto; width: 16px; height: 13px; box-sizing: border-box; }
.folder-icon { margin-top: 2px; border: 1.5px solid currentcolor; border-radius: 2px; }
.folder-icon::before { position: absolute; top: -5px; left: -1.5px; width: 7px; height: 5px; border: 1.5px solid currentcolor; border-bottom: 0; border-radius: 2px 2px 0 0; content: ''; }
.file-icon { width: 13px; height: 16px; border: 1.5px solid currentcolor; border-radius: 2px; }
.file-icon::after { position: absolute; top: 2px; right: 2px; width: 4px; height: 4px; border-top: 1px solid currentcolor; border-right: 1px solid currentcolor; content: ''; }
.material-name { position: relative; padding-left: 28px; color: var(--md-on-surface-variant); }
.material-name::before { position: absolute; top: -20px; bottom: 50%; left: 8px; width: 14px; border-bottom: 1px solid var(--md-outline-variant); border-left: 1px solid var(--md-outline-variant); content: ''; }
</style>
