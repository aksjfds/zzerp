<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

defineProps<{
  sectionName: string
  description?: string
  pageTitle?: string
  loading?: boolean
}>()
defineEmits<{ refresh: [] }>()

const router = useRouter()
const authStore = useAuthStore()

async function logout() {
  await authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <header class="page-header">
    <div>
      <span>{{ sectionName }}</span>
      <h1>{{ pageTitle || `${sectionName}工作台` }}</h1>
      <p v-if="description">{{ description }}</p>
    </div>
    <div class="actions">
      <slot name="actions">
        <ElButton :loading="loading" @click="$emit('refresh')">刷新</ElButton>
        <ElButton @click="logout">退出登录</ElButton>
      </slot>
    </div>
  </header>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; gap: 20px; align-items: center; margin-bottom: 20px; padding: 4px 0 20px; border-bottom: 1px solid var(--erp-border); }
.page-header > div:first-child { min-width: 0; }
.page-header span { color: var(--erp-primary); font-size: 13px; font-weight: 600; }
.page-header h1 { margin: 5px 0; color: var(--erp-text); font-size: 24px; font-weight: 650; line-height: 1.4; overflow-wrap: anywhere; }
.page-header p { max-width: 72ch; margin: 0; color: var(--erp-text-secondary); font-size: 13px; }
.actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.actions :deep(.el-button) { margin: 0; }
@media (max-width: 900px) { .page-header { align-items: flex-start; flex-wrap: wrap; gap: 12px; } }
@media (max-width: 600px) {
  .page-header { padding: 0 0 16px; }
  .page-header h1 { font-size: 22px; }
  .actions { width: 100%; justify-content: flex-start; }
}
</style>
