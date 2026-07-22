<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import CustomerOrdersView from '@/features/customer-orders/views/CustomerOrdersView.vue'
import { useAuthStore } from '@/stores/auth'
import AdminPageHeader from '../components/AdminPageHeader.vue'
import WorkerOverview from '@/features/workers/components/WorkerOverview.vue'
import { useAdminWorkers } from '../composables/useAdminWorkers'

const router = useRouter()
const authStore = useAuthStore()
const props = withDefaults(defineProps<{ mode?: 'admin' | 'pmc' }>(), { mode: 'admin' })
const isPmc = computed(() => props.mode === 'pmc')
const activeTab = ref<'orders' | 'workers'>('orders')
const workers = useAdminWorkers()

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
      @refresh="workers.loadWorkers"
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
          @select="workers.selectWorker"
          @month-change="workers.loadHistory"
        />
      </ElTabPane>
    </ElTabs>
  </main>
</template>

<style scoped>
.admin-page { min-height: 100vh; padding: 24px; background: var(--erp-bg); }
.admin-tabs :deep(.el-tabs__header) { margin-bottom: 14px; }
.orders-card {
  padding: 20px;
  border: 1px solid var(--erp-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}
@media (max-width: 900px) { .admin-page { padding: 12px; } }
</style>
