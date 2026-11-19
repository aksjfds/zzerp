<script setup lang="ts">
defineProps<{ sectionName: string; pageTitle?: string; loading?: boolean }>()
defineEmits<{ refresh: [] }>()
</script>
<template>
  <header class="page-heading">
    <div class="page-heading-copy"><span class="eyebrow">{{ sectionName }}</span><h1>{{ pageTitle || `${sectionName}工作台` }}</h1></div>
    <div class="page-heading-actions"><slot name="actions"><ElButton :loading="loading" @click="$emit('refresh')">刷新数据</ElButton></slot></div>
  </header>
</template>
<style scoped>
.page-heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 24px; margin-bottom: 32px; }
.page-heading-copy { min-width: 0; flex: 1 1 260px; }
.eyebrow { color: var(--erp-text-muted); font-size: 12px; font-weight: 500; }
h1 { margin: 6px 0 0; color: var(--erp-text); font-size: 30px; line-height: 1.25; font-weight: 700; letter-spacing: -.025em; overflow-wrap: anywhere; }
.page-heading-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.page-heading-actions :deep(.el-button) { margin: 0; }
@media (max-width: 900px) { .page-heading { align-items: flex-start; flex-wrap: wrap; } }
@media (max-width: 600px) { .page-heading { margin-bottom: 24px; gap: 16px; } h1 { font-size: 24px; } .page-heading-actions { width: 100%; } }
</style>
