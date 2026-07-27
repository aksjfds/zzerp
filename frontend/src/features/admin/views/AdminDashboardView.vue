<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import CustomerOrdersView from '@/features/customer-orders/views/CustomerOrdersView.vue'
import { useAuthStore } from '@/stores/auth'
import AdminPageHeader from '../components/AdminPageHeader.vue'
import WorkerOverview from '@/features/workers/components/WorkerOverview.vue'
import { useAdminWorkers } from '../composables/useAdminWorkers'
import PmcPartProgressView from './PmcPartProgressView.vue'

const router = useRouter()
const authStore = useAuthStore()
const props = withDefaults(defineProps<{ mode?: 'admin' | 'pmc' }>(), { mode: 'admin' })
const isPmc = computed(() => props.mode === 'pmc')
const activeTab = ref<'orders' | 'parts' | 'workers'>('orders')
const workers = useAdminWorkers()
const partProgressView = ref<{ load: () => Promise<void> }>()

function refresh() {
  if (isPmc.value && activeTab.value === 'parts') {
    void partProgressView.value?.load()
    return
  }
  void workers.loadWorkers()
}

async function logout() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(workers.loadWorkers)
</script>

<template>
  <main class="admin-page">
    <AdminPageHeader
      :account-label="isPmc ? 'PMC 生产计划与物料控制' : 'admin 管理员'"
      :title="isPmc ? 'PMC 看板' : '管理看板'"
      @refresh="refresh"
      @logout="logout"
    />
    <ElTabs v-model="activeTab" class="admin-tabs">
      <ElTabPane label="客户订单生产情况" name="orders">
        <section class="orders-card">
          <CustomerOrdersView
            embedded
            :read-only="isPmc"
            :show-product-progress="isPmc"
          />
        </section>
      </ElTabPane>
      <ElTabPane v-if="isPmc" label="配件生产进度" name="parts">
        <PmcPartProgressView
          ref="partProgressView"
        />
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
.orders-card {
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-sm);
}
@media (max-width: 900px) { .admin-page { padding: 16px; } }
@media (max-width: 560px) { .admin-page { padding: 12px; } .orders-card { padding: 12px; border-radius: var(--erp-radius); } }
</style>
