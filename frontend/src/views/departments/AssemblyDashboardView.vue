<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div>
        <div class="page-kicker">装配部门</div>
        <h1>装配工作台</h1>
      </div>
      <nav class="header-actions" aria-label="装配导航">
        <ElButton @click="router.push('/dashboard')">产品总览</ElButton>
        <ElButton class="nav-current" type="primary" aria-current="page">装配工作台</ElButton>
        <ElButton @click="switchUser">切换用户</ElButton>
      </nav>
    </header>
    <section class="empty-panel">
      <ElEmpty description="装配部门功能待开发" />
    </section>
  </main>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  padding: 22px;
  background: var(--erp-bg);
}
.dashboard-header,
.empty-panel {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}
.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 16px 20px;
}
.dashboard-header h1 { margin: 6px 0 0; font-size: 22px; }
.page-kicker { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.header-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.header-actions :deep(.el-button + .el-button) { margin-left: 0; }
.nav-current { pointer-events: none; }
.empty-panel { padding: 48px 20px; }
@media (max-width: 640px) {
  .dashboard-page { padding: 12px; }
  .dashboard-header { align-items: flex-start; flex-direction: column; }
  .header-actions { justify-content: flex-start; width: 100%; }
}
</style>
