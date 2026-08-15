<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CustomerOrdersView from '@/features/customer-orders/views/CustomerOrdersView.vue'
import OrderProgressDetailsView from '@/features/customer-orders/views/OrderProgressDetailsView.vue'
import { useAuthStore } from '@/stores/auth'
import AdminPageHeader from '../components/AdminPageHeader.vue'
import WorkerOverview from '@/features/workers/components/WorkerOverview.vue'
import { useAdminWorkers } from '../composables/useAdminWorkers'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const props = withDefaults(defineProps<{ mode?: 'admin' | 'pmc' }>(), { mode: 'admin' })
const isPmc = computed(() => props.mode === 'pmc')
type DashboardTab = 'orders' | 'progress' | 'workers'
const routeTab = (): DashboardTab => (
  route.query.tab === 'workers'
    ? 'workers'
    : isPmc.value
      ? 'progress'
      : 'orders'
)
const activeTab = ref<DashboardTab>(routeTab())
const workers = useAdminWorkers()

async function logout() {
  await authStore.logout()
  router.replace('/login')
}

watch(
  () => route.query.tab,
  () => {
    activeTab.value = routeTab()
  },
)
watch(activeTab, (tab) => {
  const query = { ...route.query }
  const defaultTab = isPmc.value ? 'progress' : 'orders'
  if (tab === defaultTab) {
    delete query.tab
  } else {
    query.tab = tab
  }
  delete query.orderId
  if (
    route.query.tab !== query.tab
    || route.query.orderId !== query.orderId
  ) {
    void router.replace({ query })
  }
})

onMounted(workers.loadWorkers)
</script>

<template>
  <main class="admin-page">
    <AdminPageHeader
      :account-label="isPmc ? 'PMC 生产计划与物料控制' : 'admin 管理员'"
      :title="isPmc ? 'PMC 看板' : '管理看板'"
      @logout="logout"
    />
    <ElTabs v-model="activeTab" class="admin-tabs">
      <ElTabPane v-if="!isPmc" label="客户订单生产情况" name="orders">
        <section class="dashboard-card">
          <CustomerOrdersView
            embedded
          />
        </section>
      </ElTabPane>
      <ElTabPane v-if="isPmc" label="进度明细表" name="progress" lazy>
        <section class="dashboard-card">
          <OrderProgressDetailsView />
        </section>
      </ElTabPane>
      <ElTabPane label="工人总览" name="workers">
        <WorkerOverview
          v-model:worker-keyword="workers.workerKeyword.value"
          v-model:department-filter="workers.departmentFilter.value"
          v-model:selected-month="workers.selectedMonth.value"
          :departments="workers.departments.value"
          :workers="workers.filteredWorkers.value"
          :selected-worker="workers.selectedWorker.value"
          :selected-worker-title="workers.selectedWorkerTitle.value"
          :history="workers.history.value"
          :workers-loading="workers.workersLoading.value"
          :history-loading="workers.historyLoading.value"
          :pay-summary="workers.paySummary.value"
          :pay-loading="workers.payLoading.value"
          @select="workers.selectWorker"
          @month-change="workers.loadWorkerDetails"
        />
      </ElTabPane>
    </ElTabs>
  </main>
</template>

<style scoped>
.admin-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--md-surface); }
.admin-tabs :deep(.el-tabs__header) { margin-bottom: 14px; }
.dashboard-card {
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-sm);
}
@media (max-width: 900px) { .admin-page { padding: 16px; } }
@media (max-width: 560px) { .admin-page { padding: 12px; } .dashboard-card { padding: 12px; border-radius: var(--erp-radius); } }
</style>
