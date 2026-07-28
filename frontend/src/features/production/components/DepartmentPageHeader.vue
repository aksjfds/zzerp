<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

defineProps<{
  departmentName: string
  description: string
  pageTitle?: string
  tagConfigPath?: string
  workersPath?: string
  progressPath?: string
  backPath?: string
}>()
defineEmits<{ refresh: [] }>()
const router = useRouter()
const authStore = useAuthStore()
async function logout() {
  await authStore.logout()
  router.replace('/login')
}

function navigate(path: string) {
  void router.push(path)
}
</script>

<template>
  <header class="page-header">
    <div><span>{{ departmentName }}</span><h1>{{ pageTitle || `${departmentName}工作台` }}</h1><p>{{ description }}</p></div>
    <div class="actions">
      <ElButton v-if="backPath" @click="navigate(backPath)">返回工作台</ElButton>
      <ElButton v-if="workersPath" type="primary" plain @click="navigate(workersPath)">工人管理</ElButton>
      <ElButton v-if="progressPath" type="primary" plain @click="navigate(progressPath)">查看生产进度</ElButton>
      <ElButton v-if="tagConfigPath" type="primary" plain @click="navigate(tagConfigPath)">标记与单价配置</ElButton>
      <ElButton @click="$emit('refresh')">刷新</ElButton>
      <ElButton @click="logout">退出登录</ElButton>
    </div>
  </header>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; gap: 20px; align-items: center; margin-bottom: 18px; padding: 20px 24px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 5px 0; font-size: 24px; font-weight: 600; letter-spacing: -.02em; }
.page-header p { margin: 0; color: var(--el-text-color-secondary); }
.actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.actions :deep(.el-button) { margin: 0; }
@media (max-width: 900px) { .page-header { align-items: flex-start; flex-direction: column; } }
@media (max-width: 600px) {
  .page-header { padding: 16px; }
  .actions { display: grid; width: 100%; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .actions :deep(.el-button) { width: 100%; }
}
@media (max-width: 420px) { .actions { grid-template-columns: 1fr; } }
</style>
