<script setup lang="ts">
import { computed } from 'vue'
import type {
  AssemblyMaterialArrival,
  DepartmentProductionProgressItem,
  ProductionTaskProcessingStatus,
} from '../domain/productionProgress'
import {
  buildProductionTaskRows,
  displayWorkshopName,
  productionTaskStatusPresentation,
  type ProductionTaskParentRow,
  type ProductionTaskStatusRow,
  type ProductionTaskTreeRow,
} from '../domain/productionTaskTree'

const props = defineProps<{
  items: DepartmentProductionProgressItem[]
  loading: boolean
}>()
const emit = defineEmits<{
  select: [item: DepartmentProductionProgressItem]
  viewAllWorkOrders: [item: DepartmentProductionProgressItem]
  viewWorkOrders: [
    item: DepartmentProductionProgressItem,
    status: ProductionTaskProcessingStatus,
  ]
  createWorkOrder: [
    item: DepartmentProductionProgressItem,
    status: ProductionTaskProcessingStatus,
  ]
}>()

const rows = computed(() => buildProductionTaskRows(props.items))

function isTask(row: ProductionTaskTreeRow): row is ProductionTaskParentRow {
  return row.row_type === 'task'
}

function statusType(status: ProductionTaskProcessingStatus) {
  return productionTaskStatusPresentation[status.status].type
}

function isWaitingForMaterials(
  row: ProductionTaskTreeRow,
): row is ProductionTaskStatusRow {
  return row.row_type === 'status'
    && row.status.status === 'not_started'
    && row.status.action === 'none'
    && row.task.material_arrivals.length > 0
}

function materialArrivalType(
  material: AssemblyMaterialArrival,
): 'success' | 'warning' | 'info' {
  if (material.task_quantity > 0 && material.arrived_quantity >= material.task_quantity) {
    return 'success'
  }
  return material.arrived_quantity > 0 ? 'warning' : 'info'
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
  >
    <ElTableColumn label="生产任务 / 加工状态" min-width="230">
      <template #default="{ row }">
        <div v-if="isTask(row)" class="task-cell">
          <ElLink
            class="tree-name task-name"
            type="primary"
            :underline="false"
            @click="emit('select', row.task)"
          >
            <span class="directory-icon folder-icon" aria-hidden="true" />
            <span>{{ row.task.part_name }}</span>
          </ElLink>
          <div class="task-overview-statuses">
            <ElTag
              v-for="status in row.overview_statuses"
              :key="status.key"
              :type="status.type"
              effect="light"
              size="small"
            >
              {{ status.label }}<template v-if="status.quantity !== null"> · {{ status.quantity }}</template>
            </ElTag>
          </div>
        </div>
        <div v-else class="status-cell" :class="{ 'has-next': !row.is_last_child }">
          <span
            class="tree-name status-branch"
            :class="{ 'is-last': row.is_last_child }"
          >
            <span class="directory-icon file-icon" aria-hidden="true" />
            <ElTag
              :type="statusType(row.status)"
              effect="light"
              size="small"
            >
              {{ row.status.label }} · {{ row.status.quantity }}
            </ElTag>
          </span>
          <div v-if="isWaitingForMaterials(row)" class="material-arrival-list">
            <ElTag
              v-for="material in row.task.material_arrivals"
              :key="`${material.material_type}:${material.material_no}`"
              :type="materialArrivalType(material)"
              effect="plain"
              size="small"
            >
              {{ material.material_name }} · {{ material.arrived_quantity }}/{{ material.task_quantity }}
            </ElTag>
          </div>
        </div>
      </template>
    </ElTableColumn>
    <ElTableColumn label="物料编号" min-width="145">
      <template #default="{ row }">
        {{ isTask(row) ? row.task.part_no : '—' }}
      </template>
    </ElTableColumn>
    <ElTableColumn label="车间" min-width="120">
      <template #default="{ row }">
        {{ isTask(row) ? displayWorkshopName(row.task.processing_workshop) : '—' }}
      </template>
    </ElTableColumn>
    <ElTableColumn label="加工工艺" min-width="160">
      <template #default="{ row }">
        <span v-if="isTask(row)">—</span>
        <span v-else>{{ row.status.procedure_names.join('、') || '—' }}</span>
      </template>
    </ElTableColumn>
    <ElTableColumn label="任务数" min-width="85" align="right">
      <template #default="{ row }">
        {{ isTask(row) ? row.task.task_quantity : '—' }}
      </template>
    </ElTableColumn>
    <ElTableColumn label="到货数" min-width="90" align="right">
      <template #default="{ row }">
        <template v-if="isTask(row)">
          <ElPopover
            v-if="row.task.material_arrivals.length"
            placement="bottom"
            trigger="click"
            :width="430"
          >
            <template #reference>
              <ElButton link type="primary">{{ row.task.arrived_quantity }}</ElButton>
            </template>
            <ElTable :data="row.task.material_arrivals" size="small" table-layout="auto">
              <ElTableColumn prop="material_no" label="物料编号" min-width="120" />
              <ElTableColumn prop="material_name" label="物料" min-width="130" />
              <ElTableColumn prop="task_quantity" label="任务数" min-width="70" align="right" />
              <ElTableColumn prop="arrived_quantity" label="到货数" min-width="70" align="right" />
            </ElTable>
          </ElPopover>
          <span v-else>{{ row.task.arrived_quantity }}</span>
        </template>
        <span v-else>—</span>
      </template>
    </ElTableColumn>
    <ElTableColumn label="完成数" min-width="90" align="right">
      <template #default="{ row }">
        <span v-if="isTask(row)" class="completed">{{ row.task.completed_quantity }}</span>
        <span v-else>—</span>
      </template>
    </ElTableColumn>
    <ElTableColumn label="备注" min-width="180" show-overflow-tooltip>
      <template #default="{ row }">
        {{ isTask(row) ? (row.task.remark || '—') : '—' }}
      </template>
    </ElTableColumn>
    <ElTableColumn label="操作" min-width="110" align="center">
      <template #default="{ row }">
        <ElButton
          v-if="isTask(row)"
          link
          @click="emit('viewAllWorkOrders', row.task)"
        >查看全部工单</ElButton>
        <div v-else class="task-actions">
          <ElButton
            v-if="row.status.status === 'exception'"
            link
            type="danger"
            @click="emit('viewWorkOrders', row.task, row.status)"
          >查看情况</ElButton>
          <ElTooltip
            v-else-if="row.status.action === 'create_work_order'"
            :disabled="row.task.plan_status !== 'draft'"
            content="生产计划确认后可开工单"
            placement="top"
          >
            <span>
              <ElButton
                type="primary"
                link
                :disabled="row.task.plan_status === 'draft'"
                @click="emit('createWorkOrder', row.task, row.status)"
              >
                开工单
              </ElButton>
            </span>
          </ElTooltip>
          <ElButton
            v-else-if="row.status.action === 'view_work_orders'"
            link
            @click="emit('viewWorkOrders', row.task, row.status)"
          >查看工单</ElButton>
        </div>
      </template>
    </ElTableColumn>
  </ElTable>
</template>

<style scoped>
.completed {
  color: #22c55e;
  font-weight: 700;
}

.task-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.tree-name {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.task-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.task-overview-statuses {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  padding-left: 25px;
}

.status-cell {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.material-arrival-list {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  padding-left: 30px;
}

.directory-icon {
  position: relative;
  display: inline-block;
  flex: 0 0 auto;
  box-sizing: border-box;
  color: var(--el-color-primary);
}

.folder-icon {
  width: 17px;
  height: 13px;
  margin-top: 2px;
  border: 1.5px solid currentcolor;
  border-radius: 2px;
}

.folder-icon::before {
  position: absolute;
  top: -5px;
  left: -1.5px;
  width: 8px;
  height: 5px;
  border: 1.5px solid currentcolor;
  border-bottom: 0;
  border-radius: 2px 2px 0 0;
  content: '';
}

.file-icon {
  width: 13px;
  height: 16px;
  border: 1.5px solid var(--md-outline);
  border-radius: 2px;
}

.file-icon::after {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 4px;
  height: 4px;
  border-top: 1px solid var(--md-outline);
  border-right: 1px solid var(--md-outline);
  content: '';
}

.status-branch {
  position: relative;
  min-height: 28px;
  padding-left: 30px;
}

.status-branch::before {
  position: absolute;
  top: -24px;
  bottom: 50%;
  left: 8px;
  width: 15px;
  border-bottom: 1px solid var(--md-outline-variant);
  border-left: 1px solid var(--md-outline-variant);
  content: '';
}

.status-cell.has-next::after {
  position: absolute;
  top: 14px;
  bottom: -24px;
  left: 8px;
  border-left: 1px solid var(--md-outline-variant);
  content: '';
}
</style>
