<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import CustomerOrdersView from '@/features/customer-orders/views/CustomerOrdersView.vue'
import { useAuthStore } from '@/stores/auth'
import { queryAdminWorkerHistory, queryAdminWorkerOverview } from '../api/admin'
import type {
  AdminWorker,
  AdminWorkerDepartment,
  AdminWorkerHistoryItem,
} from '../domain/types'

const router = useRouter()
const authStore = useAuthStore()
const activeTab = ref<'orders' | 'workers'>('orders')
const departments = ref<AdminWorkerDepartment[]>([])
const workersLoading = ref(false)
const historyLoading = ref(false)
const selectedWorker = ref<AdminWorker>()
const selectedMonth = ref(new Date().toISOString().slice(0, 7))
const workerKeyword = ref('')
const departmentFilter = ref<number | ''>('')
const history = ref<AdminWorkerHistoryItem[]>([])
const allWorkers = computed(() => departments.value.flatMap(item => item.workers))
const filteredWorkers = computed(() => {
  const keyword = workerKeyword.value.trim().toLowerCase()
  return allWorkers.value.filter((worker) => {
    const matchesKeyword = !keyword || worker.worker_name.toLowerCase().includes(keyword)
    const matchesDepartment = !departmentFilter.value || worker.department_id === departmentFilter.value
    return matchesKeyword && matchesDepartment
  })
})
const selectedWorkerTitle = computed(() => selectedWorker.value
  ? `${selectedWorker.value.department_name} / ${selectedWorker.value.worker_name}`
  : '请选择工人')

async function loadWorkers() {
  workersLoading.value = true
  try {
    departments.value = await queryAdminWorkerOverview()
    if (!selectedWorker.value) {
      selectedWorker.value = filteredWorkers.value[0]
      if (selectedWorker.value) await loadHistory()
    }
  } catch {
    ElMessage.error('工人总览加载失败')
  } finally {
    workersLoading.value = false
  }
}

async function loadHistory() {
  if (!selectedWorker.value) {
    history.value = []
    return
  }
  historyLoading.value = true
  try {
    history.value = await queryAdminWorkerHistory(selectedWorker.value.id, selectedMonth.value)
  } catch {
    ElMessage.error('工人工作情况加载失败')
  } finally {
    historyLoading.value = false
  }
}

async function selectWorker(worker: AdminWorker) {
  selectedWorker.value = worker
  await loadHistory()
}

async function logout() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(loadWorkers)

watch(filteredWorkers, async (workers) => {
  if (!selectedWorker.value || !workers.some(worker => worker.id === selectedWorker.value?.id)) {
    selectedWorker.value = workers[0]
    await loadHistory()
  }
})
</script>

<template>
  <main class="admin-page">
    <header class="admin-header">
      <div>
        <span>admin 管理员</span>
        <h1>管理看板</h1>
      </div>
      <div>
        <ElButton @click="loadWorkers">刷新工人总览</ElButton>
        <ElButton @click="logout">退出登录</ElButton>
      </div>
    </header>

    <ElTabs v-model="activeTab" class="admin-tabs">
      <ElTabPane label="客户订单生产情况" name="orders">
        <section class="admin-card">
          <CustomerOrdersView embedded />
        </section>
      </ElTabPane>

      <ElTabPane label="工人总览" name="workers">
        <div class="worker-layout">
          <section v-loading="workersLoading" class="admin-card worker-list">
            <div class="worker-filters">
              <ElInput v-model="workerKeyword" clearable placeholder="搜索工人名字" />
              <ElSelect v-model="departmentFilter" clearable placeholder="筛选部门">
                <ElOption
                  v-for="department in departments"
                  :key="department.department_id"
                  :label="department.department_name"
                  :value="department.department_id"
                />
              </ElSelect>
            </div>
            <div v-if="!filteredWorkers.length" class="empty-text">暂无匹配工人</div>
            <button
                v-for="worker in filteredWorkers"
                :key="worker.id"
                class="worker-card"
                :class="{ selected: selectedWorker?.id === worker.id }"
                type="button"
                @click="selectWorker(worker)"
              >
                <strong>{{ worker.worker_name }}</strong>
                <span>{{ worker.department_name }} · {{ worker.workshop_name || '部门直属' }}</span>
              </button>
          </section>

          <section class="admin-card history-panel">
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
                @change="loadHistory"
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
      </ElTabPane>
    </ElTabs>
  </main>
</template>

<style scoped>
.admin-page { min-height: 100vh; padding: 24px; background: var(--erp-bg); }
.admin-header, .admin-card {
  border: 1px solid var(--erp-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}
.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 18px;
  padding: 20px 24px;
}
.admin-header span, .history-heading span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.admin-header h1, .history-heading h2 { margin: 5px 0 0; }
.admin-tabs :deep(.el-tabs__header) { margin-bottom: 14px; }
.admin-card { padding: 20px; }
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
@media (max-width: 900px) {
  .admin-page { padding: 12px; }
  .admin-header, .history-heading { align-items: flex-start; flex-direction: column; }
  .worker-layout { grid-template-columns: 1fr; }
  .worker-list { max-height: none; }
}
</style>
