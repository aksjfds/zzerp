<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryProductionPlan, updateProductionPlan } from '../api/customerOrders'
import type { ProductionPlan, ProductionPlanItem } from '../domain/types'

const props = defineProps<{ orderId: number; editable?: boolean }>()
const emit = defineEmits<{
  updated: [plan: ProductionPlan]
  validityChange: [invalid: boolean]
}>()
const plan = ref<ProductionPlan>()
const loading = ref(false)
const saving = ref(false)
const inventoryTypeLabels = {
  part: '普通配件',
  assembly: '装配体',
  finished_product: '最终成品',
} as const
function inventoryTypeLabel(itemType: keyof typeof inventoryTypeLabels) {
  return inventoryTypeLabels[itemType]
}
function inventoryWarehouseLabel(item: ProductionPlan['inventory_items'][number]) {
  if (item.item_type === 'finished_product') return '成品仓'
  if (item.warehouse_code === '—') return '—'
  return `${item.warehouse_code} · ${item.warehouse_name}`
}
const inventoryGroups = computed(() => {
  const itemsByOrderItem = new Map<number, ProductionPlan['inventory_items']>()
  for (const item of plan.value?.inventory_items || []) {
    const items = itemsByOrderItem.get(item.customer_order_item_id) || []
    items.push(item)
    itemsByOrderItem.set(item.customer_order_item_id, items)
  }
  return (plan.value?.product_summaries || [])
    .map(summary => ({
      orderItemId: summary.customer_order_item_id,
      factoryCode: summary.product_code,
      productName: summary.product_name,
      productVersion: summary.product_version,
      items: (itemsByOrderItem.get(summary.customer_order_item_id) || [])
        .filter(item => item.available_quantity > 0),
    }))
    .filter(group => group.items.length > 0)
})
const inventoryItemCount = computed(() => inventoryGroups.value.reduce(
  (total, group) => total + group.items.length,
  0,
))
const groups = computed(() => {
  const grouped = new Map<number, ProductionPlanItem[]>()
  for (const item of plan.value?.items.filter(item => item.item_type === 'part') || []) {
    const items = grouped.get(item.customer_order_item_id) || []
    items.push(item)
    grouped.set(item.customer_order_item_id, items)
  }
  return (plan.value?.product_summaries || []).map((summary) => {
    const items = grouped.get(summary.customer_order_item_id) || []
    return {
      orderItemId: summary.customer_order_item_id,
      factoryCode: summary.product_code,
      productName: summary.product_name,
      productVersion: summary.product_version,
      orderQuantity: summary.order_quantity,
      items,
    }
  })
})
function componentFinishedCapacity(item: ProductionPlanItem, orderQuantity: number) {
  const unitRequirement = item.unit_requirement || 1
  return Math.max(0, Math.floor(
    orderQuantity
    + (item.planned_production_quantity - item.net_required_quantity) / unitRequirement,
  ))
}
function plannedFinishedQuantity(group: (typeof groups.value)[number]) {
  if (!group.items.length) return 0
  return Math.min(...group.items.map(
    item => componentFinishedCapacity(item, group.orderQuantity),
  ))
}
function groupSatisfied(group: (typeof groups.value)[number]) {
  return plannedFinishedQuantity(group) >= group.orderQuantity
}
const invalid = computed(() => !plan.value || groups.value.some(group => !groupSatisfied(group)))
watch(invalid, value => emit('validityChange', value), { immediate: true })

async function load() {
  loading.value = true
  try {
    plan.value = await queryProductionPlan(props.orderId)
    emit('updated', plan.value)
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '生产计划加载失败')
  } finally {
    loading.value = false
  }
}

async function save(options?: { silent?: boolean }) {
  if (!plan.value || invalid.value) {
    ElMessage.warning('普通配件数量按 BOM 换算后不足以满足订单需求')
    return undefined
  }
  saving.value = true
  try {
    plan.value = await updateProductionPlan(plan.value)
    emit('updated', plan.value)
    if (!options?.silent) ElMessage.success('生产计划已暂存')
    return plan.value
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '生产计划保存失败')
    return undefined
  } finally {
    saving.value = false
  }
}

defineExpose({ load, plan, save })
onMounted(load)
</script>

<template>
  <div v-loading="loading" class="plan-editor">
    <section class="inventory-panel">
      <div class="inventory-panel-heading">
        <h2>库存参考</h2>
        <ElTag effect="plain" size="small">{{ inventoryItemCount }} 项</ElTag>
      </div>
      <ElEmpty v-if="!loading && !inventoryGroups.length" description="暂无相关产品库存" />
      <div v-else class="inventory-products">
        <section
          v-for="group in inventoryGroups"
          :key="group.orderItemId"
          class="inventory-product-card"
        >
          <div class="inventory-product-heading">
            <div>
              <strong>{{ group.factoryCode }} · {{ group.productName }}</strong>
              <span>V{{ group.productVersion }}</span>
            </div>
          </div>
          <div class="inventory-items">
            <article
              v-for="item in group.items"
              :key="`${item.item_type}:${item.product_bom_id ?? item.flow_node_id}:${item.id}`"
              class="inventory-item"
            >
              <div class="inventory-item-content">
                <div class="inventory-identity">
                  <strong>{{ item.item_code }} · {{ item.item_name }}</strong>
                  <div class="inventory-meta">
                    <ElTag effect="plain" size="small">{{ inventoryTypeLabel(item.item_type) }}</ElTag>
                    <span>{{ item.processing_status }}</span>
                    <span>{{ inventoryWarehouseLabel(item) }}</span>
                  </div>
                </div>
                <div class="inventory-metrics">
                  <div>
                    <span>实存</span>
                    <strong>{{ item.stock_quantity }}</strong>
                  </div>
                  <div>
                    <span>占用</span>
                    <strong>{{ item.reserved_quantity }}</strong>
                  </div>
                  <div class="available-metric">
                    <span>可用</span>
                    <strong>{{ item.available_quantity }}</strong>
                  </div>
                </div>
              </div>
              <div v-if="item.planned_allocation_quantity" class="inventory-allocation">
                确认时{{ item.allocation_mode === 'reservation' ? '占用' : '出库' }}
                <strong>{{ item.planned_allocation_quantity }}</strong>
              </div>
            </article>
          </div>
        </section>
      </div>
    </section>

    <section class="plan-card">
      <h2>计划数量</h2>
      <ElEmpty v-if="!loading && !groups.length" description="暂无生产计划项目" />
      <section v-for="group in groups" :key="group.orderItemId" class="product-plan">
        <div class="product-heading">
          <div>
            <strong>{{ group.factoryCode }} · {{ group.productName }}</strong>
            <span>V{{ group.productVersion }}</span>
          </div>
          <div class="plan-summary">
            <div class="order-quantity">
              <span>订单数量</span>
              <strong>{{ group.orderQuantity }} 件</strong>
            </div>
          </div>
        </div>
        <ElTable v-table-column-widths="'sales.plan-items'" :data="group.items" border stripe table-layout="auto">
          <ElTableColumn prop="item_code" label="编号" min-width="130" />
          <ElTableColumn prop="item_name" label="配件" min-width="210" />
          <ElTableColumn prop="unit_requirement" label="单件用量" width="95" align="right" />
          <ElTableColumn label="净需求" width="110" align="right">
            <template #default="{ row }">{{ row.net_required_quantity }}</template>
          </ElTableColumn>
          <ElTableColumn label="计划数量" width="150" align="right">
            <template #default="{ row }">
              <ElInputNumber
                v-if="editable && plan?.status === 'draft'"
                v-model="row.planned_production_quantity"
                :min="row.net_required_quantity"
                :controls="false"
              />
              <span v-else>{{ row.planned_production_quantity }}</span>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>
    </section>
  </div>
</template>

<style scoped>
.plan-editor { display: grid; gap: 18px; }
.plan-card, .inventory-panel { padding: 18px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); }
.inventory-panel-heading { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.inventory-products { display: grid; gap: 14px; }
.inventory-product-card { overflow: hidden; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius); background: var(--md-surface); }
.inventory-product-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 14px; background: var(--md-surface-container-low); }
.inventory-product-heading > div { display: grid; gap: 2px; }
.inventory-product-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
.inventory-items { display: grid; }
.inventory-item { position: relative; padding: 13px 14px; }
.inventory-item + .inventory-item { border-top: 1px solid var(--md-outline-variant); }
.inventory-item-content { display: grid; grid-template-columns: minmax(260px, 1fr) auto; gap: 18px; align-items: center; }
.inventory-identity { display: grid; gap: 7px; min-width: 0; }
.inventory-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; color: var(--el-text-color-secondary); font-size: 12px; }
.inventory-metrics { display: grid; grid-template-columns: repeat(3, minmax(68px, 1fr)); gap: 8px; }
.inventory-metrics > div { display: grid; min-width: 68px; gap: 2px; padding: 7px 10px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); text-align: right; }
.inventory-metrics span { color: var(--el-text-color-secondary); font-size: 11px; }
.inventory-metrics strong { font-variant-numeric: tabular-nums; }
.inventory-metrics .available-metric { color: var(--erp-primary); background: var(--md-primary-container); }
.inventory-allocation { margin-top: 9px; color: var(--el-text-color-secondary); font-size: 12px; text-align: right; }
.inventory-allocation strong { margin-left: 4px; color: var(--erp-primary); }
.product-plan { margin-top: 14px; }
.product-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 8px; padding: 10px 12px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
.product-heading > div { display: grid; gap: 2px; }
.product-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
.product-heading .plan-summary { display: flex; align-items: center; gap: 10px; }
.order-quantity { display: flex; align-items: baseline; gap: 7px; padding: 7px 11px; border-radius: var(--erp-radius); color: var(--md-on-primary-container); background: var(--md-primary-container); }
.order-quantity span { color: inherit; font-size: 12px; font-weight: 600; }
.order-quantity strong { font-variant-numeric: tabular-nums; }
h2 { margin: 0; font-size: 18px; }
@media (max-width: 680px) {
  .product-heading, .inventory-product-heading { align-items: stretch; flex-direction: column; }
  .product-heading .plan-summary { justify-content: space-between; }
  .inventory-item-content { grid-template-columns: 1fr; }
  .inventory-metrics { width: 100%; }
}
</style>
