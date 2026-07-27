<script setup lang="ts">
import type { RepositoryItem } from '../domain/types'

const props = withDefaults(defineProps<{
  items: RepositoryItem[]
  loading: boolean
  selectedKey?: string | null
  allowWorkOrder?: boolean
  mode?: 'production' | 'purchase'
}>(), { mode: 'production' })
const emit = defineEmits<{
  select: [item: RepositoryItem]
  createWorkOrder: [item: RepositoryItem]
}>()
</script>

<template>
  <div v-loading="loading" class="repository-cards">
    <article
      v-for="item in items"
      :key="item.card_key"
      class="repository-card"
      :class="{ selected: item.card_key === selectedKey }"
      tabindex="0"
      @click="emit('select', item)"
      @keydown.enter="emit('select', item)"
    >
      <div class="card-heading">
        <strong>{{ item.part_no === item.part_name ? item.part_name : `${item.part_no} - ${item.part_name}` }}</strong>
        <ElTag :type="item.work_status === 'completed' ? 'success' : item.work_status === 'processing' ? 'warning' : 'info'" size="small">
          {{ item.work_status === 'processing'
            ? (props.mode === 'purchase' ? '采购中' : '加工中')
            : item.work_status === 'completed'
              ? (props.mode === 'purchase' ? '已入库' : '已完成')
              : (props.mode === 'purchase' ? '待采购' : '未加工') }}
        </ElTag>
      </div>
      <dl>
        <div><dt>产品</dt><dd>{{ item.factory_code }} · {{ item.product_name }}</dd></div>
        <div><dt>订单编号</dt><dd>{{ item.customer_order_no }}</dd></div>
        <div><dt>当前工艺</dt><dd>{{ item.procedure_name }}</dd></div>
        <div v-if="props.mode === 'production'"><dt>标记状态</dt><dd>{{ item.current_tag_set_name || '未打标记' }}</dd></div>
        <div><dt>来源节点</dt><dd>{{ item.source_node_label }}</dd></div>
        <div><dt>{{ props.mode === 'purchase' ? '需求数量' : '当前数量' }}</dt><dd>{{ item.quantity }}</dd></div>
        <div><dt>{{ props.mode === 'purchase' ? '需求时间' : '到达时间' }}</dt><dd>{{ item.arrived_at || '-' }}</dd></div>
      </dl>
      <div v-if="allowWorkOrder" class="card-actions">
        <ElButton
          type="primary"
          plain
          size="small"
          :disabled="!item.can_create_work_order"
          @click.stop="emit('createWorkOrder', item)"
        >{{ props.mode === 'purchase' ? '建外购单' : '开工单' }}</ElButton>
      </div>
    </article>
    <ElEmpty v-if="!loading && !items.length" description="当前部门暂无配件或装配体" :image-size="72" />
  </div>
</template>

<style scoped>
.repository-cards { display: grid; grid-template-columns: 1fr; gap: 12px; min-height: 150px; }
.repository-card { padding: 14px; border: 1px solid transparent; border-radius: var(--erp-radius); background: var(--md-surface-container-low); cursor: pointer; transition: background-color .16s, border-color .16s, box-shadow .16s; }
.repository-card:hover, .repository-card:focus-visible { border-color: var(--erp-primary); outline: none; }
.repository-card:hover { background: var(--md-surface-container); }
.repository-card.selected { border-color: var(--md-primary); background: var(--md-primary-container); box-shadow: none; }
.card-heading { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.card-heading strong { min-width: 0; color: var(--md-on-surface); font-size: 14px; line-height: 1.45; }
dl { margin: 13px 0 0; }
dl div { display: grid; grid-template-columns: 68px minmax(0, 1fr); gap: 8px; margin-top: 7px; font-size: 13px; }
dt { color: var(--el-text-color-secondary); }
dd { margin: 0; overflow-wrap: anywhere; }
.repository-cards :deep(.el-empty) { grid-column: 1 / -1; }
.card-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; margin-top: 12px; }
.card-actions :deep(.el-button) { width: 100%; margin: 0; }
@media (max-width: 480px) {
  .card-heading { align-items: flex-start; flex-direction: column; }
  .card-actions { grid-template-columns: 1fr; }
}
</style>
