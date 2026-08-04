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
const inventoryRows = computed(() => {
  const summaries = new Map(
    (plan.value?.product_summaries || []).map(summary => [
      summary.customer_order_item_id,
      summary,
    ]),
  )
  return (plan.value?.inventory_items || []).map(item => ({
    ...item,
    productCode: summaries.get(item.customer_order_item_id)?.product_code || '',
    productName: summaries.get(item.customer_order_item_id)?.product_name || '',
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
function itemFinishedCapacity(item: ProductionPlanItem, orderQuantity: number) {
  return Math.max(0, Math.floor(
    orderQuantity
    + (item.planned_production_quantity - item.net_required_quantity)
      / item.unit_requirement,
  ))
}
function plannedFinishedQuantity(group: (typeof groups.value)[number]) {
  if (!group.items.length) return 0
  return Math.min(...group.items.map(
    item => itemFinishedCapacity(item, group.orderQuantity),
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

async function save() {
  if (!plan.value || invalid.value) {
    ElMessage.warning('普通配件数量按 BOM 换算后不足以满足订单需求')
    return undefined
  }
  saving.value = true
  try {
    plan.value = await updateProductionPlan(plan.value)
    emit('updated', plan.value)
    ElMessage.success('生产计划已保存')
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
      <ElTable
        v-loading="loading"
        :data="inventoryRows"
        border
        stripe
        empty-text="暂无相关库存项目"
      >
        <ElTableColumn label="产品" min-width="190">
          <template #default="{ row }">
            {{ row.productCode }} · {{ row.productName }} · V{{ row.product_version }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="库存类型" width="100">
          <template #default="{ row }">{{ inventoryTypeLabel(row.item_type) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="item_code" label="编号" min-width="130" />
        <ElTableColumn prop="item_name" label="名称" min-width="170" />
        <ElTableColumn prop="current_inventory_quantity" label="当前可用库存" width="120" align="right" />
        <ElTableColumn prop="reserved_inventory_quantity" label="本计划占用" width="110" align="right" />
        <ElTableColumn prop="issued_inventory_quantity" label="本计划已出库" width="120" align="right" />
      </ElTable>
    </section>

    <section class="plan-card">
      <div class="plan-heading">
        <div>
          <h2>生产计划</h2>
          <p>只需填写普通配件的新生产数量；系统按 BOM 校验可满足的成品数量，确认时重新计算并占用库存。</p>
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
        <ElTable v-loading="loading" :data="group.items" border stripe>
          <ElTableColumn prop="item_code" label="编号" min-width="130" />
          <ElTableColumn prop="item_name" label="名称" min-width="180" />
          <ElTableColumn prop="unit_requirement" label="单件用量" width="95" align="right" />
          <ElTableColumn prop="gross_required_quantity" label="系统需求" width="105" align="right" />
          <ElTableColumn prop="net_required_quantity" label="新生产需求" width="115" align="right" />
          <ElTableColumn label="计划生产数量" width="160" align="right">
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
.inventory-card, .plan-card { padding: 20px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.plan-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 14px; }
.product-plan + .product-plan { margin-top: 18px; }
.product-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 8px; padding: 10px 12px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
.product-heading > div { display: grid; gap: 2px; }
.product-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
h2 { margin: 0; font-size: 18px; }
p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
@media (max-width: 680px) {
  .plan-heading, .product-heading { align-items: stretch; flex-direction: column; }
}
</style>
