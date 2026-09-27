<script setup lang="ts">
withDefaults(defineProps<{
  message: string
  loading?: boolean
  title?: string
  retryText?: string
}>(), { title: '数据未能更新', retryText: '重新加载' })
defineEmits<{ retry: [] }>()
</script>

<template>
  <ElAlert
    v-if="message"
    class="load-error-alert"
    :title="title"
    type="error"
    :closable="false"
    show-icon
  >
    <div class="load-error-content">
      <span>{{ message }}</span>
      <ElButton size="small" :loading="loading" @click="$emit('retry')">{{ retryText }}</ElButton>
    </div>
  </ElAlert>
</template>

<style scoped>
.load-error-alert { margin-bottom: 16px; }
.load-error-alert :deep(.el-alert__content) { flex: 1; min-width: 0; }
.load-error-content { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; padding-top: 4px; font-size: 13px; }
.load-error-content > span { flex: 1 1 220px; overflow-wrap: anywhere; }
.load-error-content :deep(.el-button) { flex-shrink: 0; }
</style>
