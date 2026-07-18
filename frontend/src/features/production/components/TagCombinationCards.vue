<script setup lang="ts">
import type { TagCard } from "../domain/types";

defineProps<{
  items: TagCard[];
  loading: boolean;
  selectedKey?: string | null;
}>();
const emit = defineEmits<{
  select: [item: TagCard];
  createWorkOrder: [item: TagCard];
}>();

function canCreateWorkOrder(item: TagCard) {
  return item.available_quantity > 0
    && ((item.repository_id === null) !== (item.tag_stock_id === null));
}
</script>

<template>
  <div v-loading="loading" class="tag-combination-cards">
    <article v-for="item in items" :key="item.card_key" class="tag-combination-card"
      :class="{ selected: item.card_key === selectedKey }" tabindex="0" @click="emit('select', item)"
      @keydown.enter="emit('select', item)">
      <dl class="tag-metrics">
        <div class="combination-name">
          <dt>标记组合名称</dt>
          <dd>{{ item.tag_set_name }}</dd>
        </div>
        <div>
          <dt>加工中</dt>
          <dd>{{ item.processing_quantity }}</dd>
        </div>
        <div>
          <dt>质检中</dt>
          <dd>{{ item.pending_qc_quantity }}</dd>
        </div>
        <div>
          <dt>已完成</dt>
          <dd>{{ item.completed_quantity }}</dd>
        </div>
      </dl>
      <ElButton
        class="create-work-order"
        type="primary"
        plain
        size="small"
        :disabled="!canCreateWorkOrder(item)"
        @click.stop="emit('createWorkOrder', item)"
      >开工单（添加标记）</ElButton>
    </article>
    <ElEmpty v-if="!loading && !items.length" description="所选配件暂无标记记录" :image-size="64" />
  </div>
</template>

<style scoped>
.tag-combination-cards {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(330px, 420px);
  gap: 12px;
  min-height: 112px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.tag-combination-card {
  padding: 14px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #f8fafc;
  cursor: pointer;
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}

.tag-combination-card:hover,
.tag-combination-card:focus-visible {
  border-color: var(--erp-primary);
  outline: none;
}

.tag-combination-card.selected {
  border-color: var(--erp-primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--erp-primary) 14%, transparent);
}

.tag-metrics {
  display: grid;
  grid-template-columns: minmax(120px, 1.7fr) repeat(3, minmax(58px, 1fr));
  gap: 8px;
  margin: 0;
}

.tag-metrics div {
  min-width: 0;
  padding: 9px;
  border-radius: 6px;
  background: #fff;
}

.tag-metrics dt {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.tag-metrics dd {
  margin: 4px 0 0;
  font-size: 17px;
  font-weight: 700;
}

.combination-name dd {
  overflow-wrap: anywhere;
  font-size: 14px;
}

.create-work-order {
  width: 100%;
  margin-top: 12px;
}
</style>
