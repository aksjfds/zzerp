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
  border: 1px solid var(--erp-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}
.admin-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.admin-header h1 { margin: 5px 0 0; }
@media (max-width: 900px) {
  .admin-header { align-items: flex-start; flex-direction: column; }
}
</style>
