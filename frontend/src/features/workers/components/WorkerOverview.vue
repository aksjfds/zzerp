<script setup lang="ts">
import type {
  WorkerHistoryItem,
  WorkerOverviewDepartment,
  WorkerOverviewItem,
} from '../domain/types'

withDefaults(defineProps<{
  departments: WorkerOverviewDepartment[]
  workers: WorkerOverviewItem[]
  selectedWorker?: WorkerOverviewItem
  selectedWorkerTitle: string
  history: WorkerHistoryItem[]
  workersLoading: boolean
  historyLoading: boolean
  showDepartmentFilter?: boolean
  allowCreate?: boolean
}>(), {
  showDepartmentFilter: true,
  allowCreate: false,
})
const workerKeyword = defineModel<string>('workerKeyword', { required: true })
const departmentFilter = defineModel<number | ''>('departmentFilter', { required: true })
const selectedMonth = defineModel<string>('selectedMonth', { required: true })
defineEmits<{
  select: [worker: WorkerOverviewItem]
  monthChange: []
  create: []
}>()
</script>

<template>
  <div class="worker-layout">
    <section v-loading="workersLoading" class="worker-panel worker-list">
      <div class="worker-filters">
        <ElInput v-model="workerKeyword" clearable placeholder="搜索工人名字" />
        <ElSelect
          v-if="showDepartmentFilter"
          v-model="departmentFilter"
          placement="top-start"
          :fallback-placements="['top-start', 'top-end']"
          clearable
          placeholder="筛选部门"
        >
          <ElOption
            v-for="department in departments"
            :key="department.department_id"
            :label="department.department_name"
            :value="department.department_id"
          />
        </ElSelect>
        <ElButton v-if="allowCreate" type="primary" @click="$emit('create')">录入工人</ElButton>
      </div>
      <div v-if="!workers.length" class="empty-text">暂无匹配工人</div>
      <button
        v-for="worker in workers"
        :key="worker.id"
        class="worker-card"
        :class="{ selected: selectedWorker?.id === worker.id }"
        type="button"
        @click="$emit('select', worker)"
      >
        <strong>{{ worker.worker_name }}</strong>
        <span>{{ worker.department_name }} · {{ worker.workshop_name || '部门直属' }}</span>
      </button>
    </section>

    <section class="worker-panel history-panel">
      <div class="history-heading">
        <div>
          <span>工人工作情况</span>
          <h2>{{ selectedWorkerTitle }}</h2>
        </div>
        <ElDatePicker
          v-model="selectedMonth"
          type="month"
          value-format="YYYY-MM"
          format="YYYY年MM月"
          placeholder="选择月份"
          :clearable="false"
          @change="$emit('monthChange')"
        />
      </div>
      <ElTable v-loading="historyLoading" :data="history" border>
        <ElTableColumn prop="item_name" label="加工配件" min-width="140" />
        <ElTableColumn prop="procedure_name" label="加工工艺" width="130" />
        <ElTableColumn prop="completed_quantity" label="加工数量" width="100" />
        <ElTableColumn label="完成率" width="100">
          <template #default="{ row }">{{ Math.round(row.completion_rate * 100) }}%</template>
        </ElTableColumn>
        <ElTableColumn prop="lost_quantity" label="遗失数" width="90" />
        <ElTableColumn prop="scrap_quantity" label="报废数" width="90" />
        <ElTableColumn prop="completed_at" label="时间" width="170" />
      </ElTable>
    </section>
  </div>
</template>

<style scoped>
.worker-panel {
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}
.worker-layout { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 18px; }
.worker-list { max-height: calc(100vh - 190px); overflow: auto; }
.worker-filters { display: grid; gap: 10px; margin-bottom: 14px; }
.empty-text { color: var(--el-text-color-secondary); font-size: 13px; }
.worker-card {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 8px;
  padding: 12px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #f8fafc;
  text-align: left;
  cursor: pointer;
}
.worker-card:hover, .worker-card.selected { border-color: var(--erp-primary); }
.worker-card.selected { box-shadow: 0 0 0 2px color-mix(in srgb, var(--erp-primary) 14%, transparent); }
.worker-card span { color: var(--el-text-color-secondary); font-size: 13px; }
.history-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.history-heading span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.history-heading h2 { margin: 5px 0 0; }
@media (max-width: 900px) {
  .history-heading { align-items: flex-start; flex-direction: column; }
  .worker-layout { grid-template-columns: 1fr; }
  .worker-list { max-height: none; }
}
</style>
