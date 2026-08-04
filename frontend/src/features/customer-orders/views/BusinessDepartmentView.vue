<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ORDER_PERMISSIONS } from '@/permission/constants'
import { useAuthStore } from '@/stores/auth'
import CustomerOrdersView from './CustomerOrdersView.vue'
import ProductionPlansView from './ProductionPlansView.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const ordersView = ref<{ load: () => Promise<void> }>()
const plansView = ref<{ load: () => Promise<void> }>()
const activeTab = computed({
  get: () => route.query.tab === 'plans' ? 'plans' : 'orders',
  set: (tab: string) => router.replace({
    path: '/business/orders',
    query: tab === 'plans' ? { tab: 'plans' } : {},
  }),
})

watch(activeTab, async (tab) => {
  await nextTick()
  if (tab === 'plans') await plansView.value?.load()
  else await ordersView.value?.load()
})

async function logout() {
  await authStore.logout()
  await router.replace('/login')
}
</script>

<template>
  <main class="business-page">
    <header class="business-header">
      <div><span>业务部</span><h1>订单与生产计划</h1></div>
      <div>
        <ElButton @click="logout">退出登录</ElButton>
        <ElButton
          v-permission="ORDER_PERMISSIONS.add"
          type="primary"
          @click="router.push('/business/orders/new')"
        >创建客户订单</ElButton>
      </div>
    </header>
    <section class="business-content">
      <ElTabs v-model="activeTab">
        <ElTabPane label="客户订单" name="orders" lazy>
          <CustomerOrdersView ref="ordersView" embedded />
        </ElTabPane>
        <ElTabPane label="生产计划" name="plans" lazy>
          <ProductionPlansView ref="plansView" />
        </ElTabPane>
      </ElTabs>
    </section>
  </main>
</template>

<style scoped>
.business-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--md-surface); }
.business-header, .business-content { border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.business-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; padding: 20px 24px; }
.business-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.business-header h1 { margin: 5px 0 0; font-size: 24px; font-weight: 600; }
.business-content { padding: 20px; }
@media (max-width: 760px) {
  .business-page { padding: 16px; }
  .business-header { align-items: stretch; flex-direction: column; gap: 16px; padding: 16px; }
  .business-header > div:last-child { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .business-header :deep(.el-button) { width: 100%; margin: 0; }
  .business-content { padding: 16px; }
}
</style>
