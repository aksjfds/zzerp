<script setup lang="ts">
withDefaults(defineProps<{
  accountLabel?: string
  title?: string
  refreshLabel?: string
}>(), {
  accountLabel: 'admin 管理员',
  title: '管理看板',
  refreshLabel: '刷新工人总览',
})
defineEmits<{ refresh: []; logout: [] }>()
</script>

<template>
  <header class="admin-header">
    <div>
      <span>{{ accountLabel }}</span>
      <h1>{{ title }}</h1>
    </div>
    <div>
      <ElButton @click="$emit('refresh')">{{ refreshLabel }}</ElButton>
      <ElButton @click="$emit('logout')">退出登录</ElButton>
    </div>
  </header>
</template>

<style scoped>
.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 18px;
  padding: 20px 24px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-sm);
}
.admin-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.admin-header h1 { margin: 5px 0 0; font-size: 24px; font-weight: 600; letter-spacing: -.02em; }
@media (max-width: 900px) {
  .admin-header { align-items: flex-start; flex-direction: column; }
}
@media (max-width: 600px) {
  .admin-header { padding: 16px; }
  .admin-header > div:last-child { display: grid; width: 100%; grid-template-columns: 1fr; gap: 8px; }
  .admin-header :deep(.el-button) { width: 100%; margin: 0; }
}
</style>
