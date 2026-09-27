<script setup lang="ts">
import { computed, toRef } from 'vue'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { useClosingSnapshot } from '@/shared/motion/useClosingSnapshot'
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
const { detail, loading, loadError, reload } = useProductionProgressDetail(
  toRef(props, 'modelValue'),
  toRef(props, 'departmentCode'),
  toRef(props, 'item'),
)
const { display, closing, beginClose, finishClose } = useClosingSnapshot(visible, () => ({
  detail: detail.value,
  loading: loading.value,
  error: loadError.value,
  item: props.item,
}), () => { visible.value = false })

function isFocused(card: ProductionProgressProcedureCard) {
  return Boolean(
    display.value.item?.processing_workshop
    && card.flow_node_id === display.value.item.flow_node_id,
  )
}
</script>

<template>
  <ElDrawer
    v-model="visible"
    title="生产情况"
    size="72%"
    destroy-on-close
    class="production-progress-drawer"
    @close="beginClose"
    @closed="finishClose"
  >
    <div v-loading="display.loading" class="drawer-body" :inert="closing || !visible">
      <LoadErrorAlert v-if="display.error" :message="display.error" :loading="loading" @retry="reload" />
      <template v-else-if="display.detail">
        <header class="item-header">
          <div>
            <p class="item-kicker">订单 {{ display.detail.customer_order_no }}</p>
            <h2>
              <template v-if="display.detail.part_no && display.detail.part_no !== display.detail.part_name">{{ display.detail.part_no }} · </template>{{ display.detail.part_name }}
            </h2>
            <p>{{ display.detail.factory_code }} · {{ display.detail.product_name }}</p>
          </div>
          <div class="item-header-meta">
            <ElTag effect="light">{{ planStatusLabels[display.detail.plan_status] }}</ElTag>
            <strong>计划任务 {{ display.detail.task_quantity }}</strong>
          </div>
        </header>

        <div v-if="display.detail.cards.length" class="tag-card-grid">
          <ProductionProgressCard
            v-for="card in display.detail.cards"
            :key="card.card_key"
            :card="card"
            :focused="isFocused(card)"
          />
        </div>
        <ElEmpty v-else description="该生产项暂无工艺记录" />
      </template>
      <ElEmpty v-else-if="!display.loading" description="请选择生产任务查看详情" />
    </div>
  </ElDrawer>
</template>

<style scoped>
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
