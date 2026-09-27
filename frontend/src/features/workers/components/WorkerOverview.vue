<script setup lang="ts">
import { ref } from 'vue'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
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
  workersError?: string
  historyError?: string
  payError?: string
  showDepartmentFilter?: boolean
  allowCreate?: boolean
  allowManage?: boolean
}>(), {
  showDepartmentFilter: true,
  allowCreate: false,
  allowManage: false,
  payLoading: false,
  workersError: '',
  historyError: '',
  payError: '',
})
const detailView = ref<'history' | 'pay'>('history')
const workerKeyword = defineModel<string>('workerKeyword', { required: true })
const departmentFilter = defineModel<number | ''>('departmentFilter', { required: true })
const selectedMonth = defineModel<string>('selectedMonth', { required: true })
defineEmits<{
  select: [worker: WorkerOverviewItem]
  monthChange: []
  create: []
  edit: [worker: WorkerOverviewItem]
  delete: [worker: WorkerOverviewItem]
  retryWorkers: []
  retryHistory: []
  retryPay: []
}>()

function money(value: MoneyValue | null | undefined) {
  return Number(value || 0).toFixed(2)
}
</script>

<template>
  <div class="worker-layout">
    <section v-loading="workersLoading" class="worker-panel worker-list">
      <div class="worker-filters">
        <ElInput v-model="workerKeyword" clearable placeholder="搜索工人名字" aria-label="搜索工人名字" />
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
      <LoadErrorAlert :message="workersError" :loading="workersLoading" @retry="$emit('retryWorkers')" />
      <div v-if="!workersLoading && !workersError && !workers.length" class="empty-text">
        {{ workerKeyword.trim() ? '没有匹配的工人，请调整搜索条件' : '暂无工人' }}
      </div>
      <button
        v-for="worker in workers"
        :key="worker.id"
        class="worker-card"
        :class="{ selected: selectedWorker?.id === worker.id }"
        :aria-pressed="selectedWorker?.id === worker.id"
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
        <div v-if="allowManage && selectedWorker" class="worker-actions">
          <ElButton @click="$emit('edit', selectedWorker)">更正资料</ElButton>
          <ElButton type="danger" plain @click="$emit('delete', selectedWorker)">删除</ElButton>
        </div>
        <ElDatePicker
          v-model="selectedMonth"
          placement="top-start"
          :fallback-placements="['top-start', 'top-end']"
          type="month"
          value-format="YYYY-MM"
          format="YYYY年MM月"
          placeholder="选择月份"
          :clearable="false"
          @change="$emit('monthChange')"
        />
      </div>
      <ElEmpty v-if="!selectedWorker" description="选择工人后查看工作记录和计件工资" :image-size="72" />
      <ElTabs v-else v-model="detailView" class="worker-detail-tabs">
        <ElTabPane label="工作记录" name="history">
          <LoadErrorAlert :message="historyError" :loading="historyLoading" @retry="$emit('retryHistory')" />
          <ElTable
            v-if="!historyError"
            v-table-column-widths="'workers.history'"
            v-loading="historyLoading"
            :data="history"
            border
            table-layout="auto"
            :empty-text="historyLoading ? '正在加载工作记录…' : '本月暂无工作记录'"
          >
            <ElTableColumn prop="item_name" label="加工配件" min-width="140" />
            <ElTableColumn prop="procedure_name" label="加工工艺" width="130" />
            <ElTableColumn prop="completed_quantity" label="加工数量" width="100" align="right" />
            <ElTableColumn label="完成率" width="100" align="right">
              <template #default="{ row }">{{ Math.round(row.completion_rate * 100) }}%</template>
            </ElTableColumn>
            <ElTableColumn prop="lost_quantity" label="遗失数" width="90" align="right" />
            <ElTableColumn prop="scrap_quantity" label="报废数" width="90" align="right" />
            <ElTableColumn prop="completed_at" label="时间" width="170" />
          </ElTable>
        </ElTabPane>
        <ElTabPane label="计件工资" name="pay">
          <LoadErrorAlert :message="payError" :loading="payLoading" @retry="$emit('retryPay')" />
          <div v-if="!payError" v-loading="payLoading" class="pay-content">
            <template v-if="paySummary">
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
              <ElTable v-table-column-widths="'workers.pay-summary'" :data="paySummary?.items || []" border table-layout="auto" empty-text="本月暂无计件工资">
                <ElTableColumn prop="item_name" label="加工配件" min-width="220" />
                <ElTableColumn prop="qualified_quantity" label="合格数量" width="100" align="right" />
                <ElTableColumn label="单件工资" width="110" align="right">
                  <template #default="{ row }">
                    {{ row.unit_price == null ? '未配置' : `¥ ${money(row.unit_price)}` }}
                  </template>
                </ElTableColumn>
                <ElTableColumn label="小计" width="120" align="right">
                  <template #default="{ row }">
                    {{ row.pay_amount == null ? '—' : `¥ ${money(row.pay_amount)}` }}
                  </template>
                </ElTableColumn>
              </ElTable>
            </template>
            <div v-else class="empty-text pay-loading">正在加载计件工资…</div>
          </div>
        </ElTabPane>
      </ElTabs>
    </section>
  </div>
</template>

<style scoped>
.worker-panel {
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-sm);
}
.worker-layout { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 18px; }
.worker-list { max-height: calc(100vh - 190px); overflow: auto; }
.worker-filters { display: grid; gap: 10px; margin-bottom: 14px; }
.empty-text { padding: 16px 0; color: var(--erp-text-secondary); font-size: 13px; line-height: 1.6; }
.pay-loading { min-height: 120px; display: grid; place-items: center; }
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
.worker-card strong, .worker-card span { overflow-wrap: anywhere; }
.worker-card span { color: var(--el-text-color-secondary); font-size: 13px; }
.history-heading { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.history-heading > div:first-child { min-width: 0; }
.worker-actions { display: flex; gap: 8px; margin-left: auto; }
.history-heading span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.history-heading h2 { margin: 5px 0 0; font-size: 20px; overflow-wrap: anywhere; }
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
.pay-summary strong { font-size: 22px; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.pay-summary .warning strong { color: var(--el-color-warning); }
@media (max-width: 900px) {
  .history-heading { align-items: flex-start; flex-direction: column; }
  .worker-layout { grid-template-columns: 1fr; }
  .worker-list { max-height: 360px; }
  .worker-filters { position: sticky; z-index: 2; top: -20px; margin: -1px -1px 14px; padding-block: 1px 10px; background: var(--erp-surface); }
  .worker-actions { margin-left: 0; flex-wrap: wrap; }
}
@media (max-width: 560px) {
  .worker-panel { padding: 14px; border-radius: var(--erp-radius); }
  .history-heading :deep(.el-date-editor) { width: 100%; }
  .pay-summary { grid-template-columns: 1fr; }
}
</style>
