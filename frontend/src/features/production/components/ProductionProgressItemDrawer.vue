<script setup lang="ts">
import { computed, toRef } from 'vue'
import ProductionProgressCard from './ProductionProgressCard.vue'
import { useProductionProgressDetail } from '../composables/useProductionProgressDetail'
import type {
  DepartmentProductionProgressItem,
  ProductionProgressProcedureCard,
} from '../domain/productionProgress'
import { planStatusLabels } from '../domain/progressPresentation'

const props = defineProps<{
  modelValue: boolean
  departmentCode: string
  item: DepartmentProductionProgressItem | null
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const { detail, loading } = useProductionProgressDetail(
  toRef(props, 'modelValue'),
  toRef(props, 'departmentCode'),
  toRef(props, 'item'),
)

function isFocused(card: ProductionProgressProcedureCard) {
  return Boolean(
    props.item?.processing_workshop
    && (props.item.flow_node_id
      ? card.flow_node_id === props.item.flow_node_id
      : card.workshop_name === props.item.processing_workshop),
  )
}
</script>

<template>
  <ElDrawer
    v-model="visible"
    title="生产情况"
    size="72%"
    destroy-on-close
    modal-class="production-progress-overlay"
    class="production-progress-drawer"
  >
    <div v-loading="loading" class="drawer-body">
      <template v-if="detail">
        <header class="item-header">
          <div>
            <p class="item-kicker">订单 {{ detail.customer_order_no }}</p>
            <h2>{{ detail.part_no }} · {{ detail.part_name }}</h2>
            <p>{{ detail.factory_code }} · {{ detail.product_name }}</p>
          </div>
          <div class="item-header-meta">
            <ElTag effect="light">{{ planStatusLabels[detail.plan_status] }}</ElTag>
            <strong>计划任务 {{ detail.task_quantity }}</strong>
          </div>
        </header>

        <div v-if="detail.cards.length" class="tag-card-grid">
          <ProductionProgressCard
            v-for="card in detail.cards"
            :key="card.card_key"
            :card="card"
            :focused="isFocused(card)"
          />
        </div>
        <ElEmpty v-else description="该生产项暂无工艺记录" />
      </template>
      <ElEmpty v-else-if="!loading" description="生产情况未加载" />
    </div>
  </ElDrawer>
</template>

<style scoped>
:global(.el-overlay.is-drawer.production-progress-overlay) {
  --erp-drawer-transition-duration: 300ms;
  background-color: transparent !important;
}
.drawer-body { min-height: 360px; }
.item-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 18px 20px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-low); }
.item-header h2, .item-header p { margin: 0; }
.item-header h2 { margin: 4px 0; font-size: 20px; }
.item-kicker { color: var(--md-on-surface-variant); }
.item-header-meta { display: flex; align-items: center; gap: 12px; white-space: nowrap; }
.tag-card-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; margin-top: 16px; }
@media (max-width: 680px) {
  .item-header, .item-header-meta { align-items: flex-start; flex-direction: column; }
}
</style>
