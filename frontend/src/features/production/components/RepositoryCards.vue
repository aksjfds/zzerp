<script setup lang="ts">
import type { RepositoryItem } from '../domain/types'

defineProps<{ items: RepositoryItem[]; loading: boolean }>()
</script>

<template>
  <div v-loading="loading" class="repository-cards">
    <article v-for="item in items" :key="item.id" class="repository-card">
      <div class="card-heading">
        <strong>{{ item.part_no }} - {{ item.part_name }}</strong>
      </div>
      <dl>
        <div><dt>订单编号</dt><dd>{{ item.customer_order_no }}</dd></div>
        <div><dt>当前工艺</dt><dd>{{ item.procedure_name }}</dd></div>
        <div><dt>数量</dt><dd>{{ item.quantity }}</dd></div>
      </dl>
    </article>
    <ElEmpty v-if="!loading && !items.length" description="当前部门暂无配件或装配体" :image-size="72" />
  </div>
</template>

<style scoped>
.repository-cards { display: grid; grid-template-columns: 1fr; gap: 12px; min-height: 150px; }
.repository-card { padding: 14px; border: 1px solid var(--erp-border); border-radius: 8px; background: #f8fafc; }
.card-heading { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.card-heading strong { min-width: 0; color: var(--erp-text); font-size: 14px; line-height: 1.45; }
dl { margin: 13px 0 0; }
dl div { display: grid; grid-template-columns: 68px minmax(0, 1fr); gap: 8px; margin-top: 7px; font-size: 13px; }
dt { color: var(--el-text-color-secondary); }
dd { margin: 0; overflow-wrap: anywhere; }
.repository-cards :deep(.el-empty) { grid-column: 1 / -1; }
</style>
