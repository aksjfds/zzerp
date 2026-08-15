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
type InventoryGroup = {
  orderItemId: number
  factoryCode: string
  productName: string
  productVersion: number
  items: ProductionPlan['inventory_items']
}
const inventoryTypeLabels = {
  part: '普通配件',
  assembly: '装配体',
  finished_product: '最终成品',
} as const
function inventoryTypeLabel(itemType: keyof typeof inventoryTypeLabels) {
  return inventoryTypeLabels[itemType]
}
function productDecomposition(group: InventoryGroup) {
  const parts = new Map<number, {
    product_bom_id: number
    item_code: string
    item_name: string
    quantity: number
  }>()
  let finishedQuantity = 0
  for (const item of group.items) {
    finishedQuantity += item.decomposition.finished_equivalent_quantity
    for (const part of item.decomposition.parts) {
      const existing = parts.get(part.product_bom_id)
      if (existing) existing.quantity += part.quantity
      else parts.set(part.product_bom_id, { ...part })
    }
  }
  return { finishedQuantity, parts: [...parts.values()] }
}
const inventoryGroups = computed(() => {
  const itemsByOrderItem = new Map<number, ProductionPlan['inventory_items']>()
  for (const item of plan.value?.inventory_items || []) {
    const items = itemsByOrderItem.get(item.customer_order_item_id) || []
    items.push(item)
    itemsByOrderItem.set(item.customer_order_item_id, items)
  }
  return (plan.value?.product_summaries || []).map(summary => ({
    orderItemId: summary.customer_order_item_id,
    factoryCode: summary.product_code,
    productName: summary.product_name,
    productVersion: summary.product_version,
    items: itemsByOrderItem.get(summary.customer_order_item_id) || [],
  }))
})
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
function componentGroups(items: ProductionPlanItem[]) {
  const grouped = new Map<number, ProductionPlanItem[]>()
  for (const item of items) {
    const key = item.product_bom_id ?? item.id
    const routes = grouped.get(key) || []
    routes.push(item)
    grouped.set(key, routes)
  }
  return [...grouped.values()]
}
function componentFinishedCapacity(items: ProductionPlanItem[], orderQuantity: number) {
  const unitRequirement = items[0]?.unit_requirement || 1
  return Math.max(0, Math.floor(
    orderQuantity
    + (items.reduce((total, item) => total + item.planned_production_quantity, 0)
      - items.reduce((total, item) => total + item.net_required_quantity, 0))
      / unitRequirement,
  ))
}
function plannedFinishedQuantity(group: (typeof groups.value)[number]) {
  if (!group.items.length) return 0
  return Math.min(...componentGroups(group.items).map(
    items => componentFinishedCapacity(items, group.orderQuantity),
  ))
}
function minimumPlanQuantity(groupItems: ProductionPlanItem[], item: ProductionPlanItem) {
  const routeCount = groupItems.filter(route => route.product_bom_id === item.product_bom_id).length
  return routeCount > 1 ? 0 : item.net_required_quantity
}
function sharedRequirement(groupItems: ProductionPlanItem[], item: ProductionPlanItem) {
  return Math.max(
    ...groupItems
      .filter(route => route.product_bom_id === item.product_bom_id)
      .map(route => route.gross_required_quantity),
    0,
  )
}
function sharedNetRequirement(groupItems: ProductionPlanItem[], item: ProductionPlanItem) {
  return Math.max(
    ...groupItems
      .filter(route => route.product_bom_id === item.product_bom_id)
      .map(route => route.net_required_quantity),
    0,
  )
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
  <div class="plan-editor">
    <section class="inventory-card">
      <div class="plan-heading">
        <div>
          <h2>库存</h2>
          <p>展示当前未被其他计划占用的库存；确认生产计划时系统会重新核算。</p>
        </div>
      </div>
      <ElEmpty v-if="!loading && !inventoryGroups.length" description="暂无相关产品库存" />
      <section
        v-for="group in inventoryGroups"
        :key="group.orderItemId"
        v-loading="loading"
        class="inventory-product"
      >
        <div class="inventory-product-heading">
          <div>
            <strong>{{ group.factoryCode }} · {{ group.productName }}</strong>
            <span>V{{ group.productVersion }}</span>
          </div>
          <ElPopover
            placement="bottom-end"
            trigger="click"
            :width="620"
          >
            <template #reference>
              <ElButton plain type="primary">查看库存换算</ElButton>
            </template>
            <div class="decomposition-heading">
              <div>
                <strong>{{ group.factoryCode }} · {{ group.productName }}</strong>
                <span>V{{ group.productVersion }} · 汇总当前全部可用库存</span>
              </div>
              <ElTag type="success" effect="light">
                成品等值 {{ productDecomposition(group).finishedQuantity }} 件
              </ElTag>
            </div>
            <p class="decomposition-note">将该产品的配件、装配体和成品库存统一换算；仅供查看，不会改变实际库存。</p>
            <ElTable
              :data="productDecomposition(group).parts"
              border
              stripe
              max-height="360"
              empty-text="该产品没有可展开的配件库存"
            >
              <ElTableColumn prop="item_code" label="配件编号" min-width="140" />
              <ElTableColumn prop="item_name" label="配件名称" min-width="180" />
              <ElTableColumn prop="quantity" label="配件等值数量" width="140" align="right" />
            </ElTable>
          </ElPopover>
        </div>
        <ElTable
          :data="group.items"
          border
          stripe
          table-layout="auto"
          empty-text="该产品暂无相关库存"
        >
          <ElTableColumn label="库存类型" width="100">
            <template #default="{ row }">{{ inventoryTypeLabel(row.item_type) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="item_code" label="编号" min-width="130" />
          <ElTableColumn prop="item_name" label="名称" min-width="170" />
          <ElTableColumn prop="completed_node_label" label="完成状态" min-width="120">
            <template #default="{ row }">{{ row.completed_node_label === '—' ? '—' : `${row.completed_node_label}完` }}</template>
          </ElTableColumn>
          <ElTableColumn prop="current_inventory_quantity" label="当前可用库存" width="120" align="right" />
          <ElTableColumn prop="reserved_inventory_quantity" label="本计划占用" width="110" align="right" />
          <ElTableColumn prop="issued_inventory_quantity" label="本计划已出库" width="120" align="right" />
        </ElTable>
      </section>
    </section>

    <section class="plan-card">
      <div class="plan-heading">
        <div>
          <h2>生产计划</h2>
          <p>填写各配件路线的新生产数量；同一配件的自产、外购路线合计满足 BOM 需求即可，确认时系统重新计算并占用库存。</p>
        </div>
      </div>
      <ElEmpty v-if="!loading && !groups.length" description="暂无生产计划项目" />
      <section v-for="group in groups" :key="group.orderItemId" class="product-plan">
        <div class="product-heading">
          <div>
            <strong>{{ group.factoryCode }} · {{ group.productName }}</strong>
            <span>V{{ group.productVersion }} · 客户需求 {{ group.orderQuantity }}</span>
          </div>
          <ElTag :type="groupSatisfied(group) ? 'success' : 'danger'">
            BOM 最多可满足 {{ plannedFinishedQuantity(group) }} 件
          </ElTag>
        </div>
        <ElTable v-loading="loading" :data="group.items" border stripe table-layout="auto">
          <ElTableColumn prop="item_code" label="编号" min-width="130" />
          <ElTableColumn prop="item_name" label="配件 / 供应路线" min-width="210" />
          <ElTableColumn prop="unit_requirement" label="单件用量" width="95" align="right" />
          <ElTableColumn label="配件总需求" width="110" align="right">
            <template #default="{ row }">{{ sharedRequirement(group.items, row) }}</template>
          </ElTableColumn>
          <ElTableColumn label="待分配数量" width="115" align="right">
            <template #default="{ row }">{{ sharedNetRequirement(group.items, row) }}</template>
          </ElTableColumn>
          <ElTableColumn label="计划生产数量" width="160" align="right">
            <template #default="{ row }">
              <ElInputNumber
                v-if="editable && plan?.status === 'draft'"
                v-model="row.planned_production_quantity"
                :min="minimumPlanQuantity(group.items, row)"
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
.inventory-card, .plan-card { padding: 20px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.plan-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 14px; }
.inventory-product + .inventory-product { margin-top: 18px; }
.inventory-product-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 8px; padding: 10px 12px; border-left: 3px solid var(--erp-primary); border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
.inventory-product-heading > div { display: grid; gap: 2px; }
.inventory-product-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
.product-plan + .product-plan { margin-top: 18px; }
.product-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 8px; padding: 10px 12px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
.product-heading > div { display: grid; gap: 2px; }
.product-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
.decomposition-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 14px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
.decomposition-heading > div { display: grid; gap: 4px; }
.decomposition-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
.decomposition-note { margin: 12px 0; }
h2 { margin: 0; font-size: 18px; }
p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
@media (max-width: 680px) {
  .plan-heading, .product-heading, .inventory-product-heading, .decomposition-heading { align-items: stretch; flex-direction: column; }
}
</style>
