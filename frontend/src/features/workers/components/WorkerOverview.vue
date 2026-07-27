<script setup lang="ts">
import { ref } from 'vue'
import type {
  WorkerHistoryItem,
  MoneyValue,
  WorkerOverviewDepartment,
  WorkerOverviewItem,
  WorkerPaySummary,
} from '../domain/types'

withDefaults(defineProps<{
  departments: WorkerOverviewDepartment[]
  workers: WorkerOverviewItem[]
  selectedWorker?: WorkerOverviewItem
  selectedWorkerTitle: string
  history: WorkerHistoryItem[]
  paySummary?: WorkerPaySummary
  workersLoading: boolean
  historyLoading: boolean
  payLoading?: boolean
  showDepartmentFilter?: boolean
  allowCreate?: boolean
}>(), {
  showDepartmentFilter: true,
  allowCreate: false,
  payLoading: false,
})
const detailView = ref<'history' | 'pay'>('history')
const workerKeyword = defineModel<string>('workerKeyword', { required: true })
const departmentFilter = defineModel<number | ''>('departmentFilter', { required: true })
const selectedMonth = defineModel<string>('selectedMonth', { required: true })
defineEmits<{
  select: [worker: WorkerOverviewItem]
  monthChange: []
  create: []
}>()

function money(value: MoneyValue | null | undefined) {
  return Number(value || 0).toFixed(2)
}
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
      <ElTabs v-model="detailView" class="worker-detail-tabs">
        <ElTabPane label="工作记录" name="history">
          <ElTable
            v-loading="historyLoading"
            :data="history"
            border
          >
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
        </ElTabPane>
        <ElTabPane label="计件工资" name="pay">
          <div v-loading="payLoading" class="pay-content">
            <div class="pay-summary">
              <div>
                <span>本月合格计件</span>
                <strong>{{ paySummary?.qualified_quantity || 0 }}</strong>
              </div>
              <div>
                <span>本月工资</span>
                <strong>¥ {{ money(paySummary?.total_pay) }}</strong>
              </div>
              <div :class="{ warning: paySummary?.unpriced_quantity }">
                <span>未计价数量</span>
                <strong>{{ paySummary?.unpriced_quantity || 0 }}</strong>
              </div>
            </div>
            <ElAlert
              v-if="paySummary?.unpriced_quantity"
              type="warning"
              :closable="false"
              title="部分历史工单没有计件单价快照，未计入工资总额"
            />
            <ElTable :data="paySummary?.items || []" border empty-text="本月暂无计件工资">
              <ElTableColumn prop="item_name" label="加工配件" min-width="220" />
              <ElTableColumn label="标记" min-width="140">
                <template #default="{ row }">
                  {{ row.tag_names.length ? row.tag_names.join('、') : '未配置' }}
                </template>
              </ElTableColumn>
              <ElTableColumn prop="qualified_quantity" label="合格数量" width="100" />
              <ElTableColumn label="单件工资" width="110">
                <template #default="{ row }">
                  {{ row.unit_price == null ? '未配置' : `¥ ${money(row.unit_price)}` }}
                </template>
              </ElTableColumn>
              <ElTableColumn label="小计" width="120">
                <template #default="{ row }">
                  {{ row.pay_amount == null ? '—' : `¥ ${money(row.pay_amount)}` }}
                </template>
              </ElTableColumn>
            </ElTable>
          </div>
        </ElTabPane>
      </ElTabs>
    </section>
  </div>
</template>

<style scoped>
.worker-panel {
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
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
  border: 1px solid transparent;
  border-radius: var(--erp-radius);
  background: var(--md-surface-container-low);
  text-align: left;
  cursor: pointer;
}
.worker-card:hover, .worker-card.selected { border-color: var(--erp-primary); }
.worker-card:hover { background: var(--md-surface-container); }
.worker-card.selected { background: var(--md-primary-container); box-shadow: none; }
.worker-card span { color: var(--el-text-color-secondary); font-size: 13px; }
.history-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.history-heading span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.history-heading h2 { margin: 5px 0 0; }
.worker-detail-tabs :deep(.el-tabs__header) { margin-bottom: 14px; }
.pay-content { display: grid; gap: 14px; min-height: 160px; }
.pay-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.pay-summary div {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: var(--erp-radius);
  background: var(--md-surface-container-low);
}
.pay-summary span { color: var(--el-text-color-secondary); font-size: 12px; }
.pay-summary strong { font-size: 22px; font-variant-numeric: tabular-nums; }
.pay-summary .warning strong { color: var(--el-color-warning); }
@media (max-width: 900px) {
  .history-heading { align-items: flex-start; flex-direction: column; }
  .worker-layout { grid-template-columns: 1fr; }
  .worker-list { max-height: none; }
}
@media (max-width: 560px) {
  .worker-panel { padding: 14px; border-radius: var(--erp-radius); }
  .history-heading :deep(.el-date-editor) { width: 100%; }
  .pay-summary { grid-template-columns: 1fr; }
}
</style>
