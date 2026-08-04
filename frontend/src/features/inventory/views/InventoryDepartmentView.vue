<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '@/features/production/components/DepartmentPageHeader.vue'
import FinishedOrderOperations from '../components/FinishedOrderOperations.vue'
import {
  issueOutboundPlan,
  queryOutboundPlans,
  queryStocks,
  queryTransactions,
} from '../api/inventory'
import type {
  InventoryDepartment,
  InventoryOutboundPlan,
  InventoryStock,
  InventoryTransaction,
} from '../domain/types'

const props = withDefaults(defineProps<{
  departmentCode?: InventoryDepartment
  title?: string
  showHeader?: boolean
  showOrderFinishedOperations?: boolean
}>(), {
  departmentCode: 'warehouse',
  title: '仓库',
  showHeader: true,
  showOrderFinishedOperations: false,
})
const loading = ref(false)
const stocks = ref<InventoryStock[]>([])
const plans = ref<InventoryOutboundPlan[]>([])
const transactions = ref<InventoryTransaction[]>([])
const finishedReceiptOperations = ref<InstanceType<typeof FinishedOrderOperations>>()
const finishedShipmentOperations = ref<InstanceType<typeof FinishedOrderOperations>>()
const itemTypeLabels = { part: '普通配件', assembly: '装配体', finished_product: '成品' } as const
const transactionLabels: Record<string, string> = {
  receipt: '入库', reserve: '占用', release: '解除占用', issue: '出库',
  adjust_in: '调整入库', adjust_out: '调整出库',
  finished_receipt: '成品入库', finished_stock_issue: '库存转入订单',
  customer_shipment: '客户发货',
}
const departmentLabel = props.departmentCode === 'finished' ? '成品部' : '仓库'
const outboundTabLabel = props.departmentCode === 'finished' ? '生产计划领用' : '生产计划出库'
const stockTabLabel = props.departmentCode === 'finished' ? '成品库存' : '库存'

function fillAll(plan: InventoryOutboundPlan) {
  plan.items.forEach((item) => {
    item.issue_quantity = item.remaining_quantity
  })
}

async function load() {
  loading.value = true
  try {
    const [nextStocks, nextPlans, nextTransactions] = await Promise.all([
      queryStocks(props.departmentCode),
      queryOutboundPlans(props.departmentCode),
      queryTransactions(props.departmentCode),
    ])
    stocks.value = nextStocks
    plans.value = nextPlans
    transactions.value = nextTransactions
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || `${departmentLabel}数据加载失败`)
  } finally {
    loading.value = false
  }
}

async function issue(plan: InventoryOutboundPlan) {
  const total = plan.items.reduce((sum, item) => sum + (item.issue_quantity || 0), 0)
  if (!total) {
    ElMessage.warning('请填写本次出库数量')
    return
  }
  try {
    await ElMessageBox.confirm(
      props.departmentCode === 'finished'
        ? `确认将成品库存转入订单 ${plan.customer_order_no}，共 ${total} 件？操作后生产计划不能取消。`
        : `确认按生产计划为订单 ${plan.customer_order_no} 出库，共 ${total} 件？出库后生产计划不能取消。`,
      props.departmentCode === 'finished' ? '成品库存领用确认' : '仓库出库确认',
      { type: 'warning' },
    )
    await issueOutboundPlan(plan)
    ElMessage.success(
      props.departmentCode === 'finished' ? '成品库存已转入订单' : '仓库库存已出库',
    )
    await load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '出库失败')
    }
  }
}

async function refreshFinishedOperations() {
  await Promise.all([
    load(),
    finishedReceiptOperations.value?.load(),
    finishedShipmentOperations.value?.load(),
  ])
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <section v-loading="loading" class="inventory-page">
    <DepartmentPageHeader
      v-if="showHeader"
      :department-name="title"
      description="跨订单库存、占用、出入库及流水。"
      @refresh="load"
    />
    <div v-else class="embedded-heading"><h2>{{ title }}</h2><ElButton @click="load">刷新</ElButton></div>
    <ElTabs>
      <ElTabPane
        v-if="showOrderFinishedOperations"
        label="成品入库"
      >
        <FinishedOrderOperations
          ref="finishedReceiptOperations"
          :show-header="false"
          mode="receipt"
          @updated="refreshFinishedOperations"
        />
      </ElTabPane>
      <ElTabPane
        v-if="showOrderFinishedOperations"
        label="订单发货"
      >
        <FinishedOrderOperations
          ref="finishedShipmentOperations"
          :show-header="false"
          mode="shipment"
          @updated="refreshFinishedOperations"
        />
      </ElTabPane>
      <ElTabPane :label="outboundTabLabel">
        <ElEmpty
          v-if="!plans.length"
          :description="departmentCode === 'finished' ? '暂无待转入订单的成品库存' : '暂无待出库占用'"
        />
        <section v-for="plan in plans" :key="plan.production_plan_id" class="plan-card">
          <div class="plan-title">
            <b>订单 {{ plan.customer_order_no }}</b>
            <div class="plan-actions">
              <ElButton @click="fillAll(plan)">全部填入</ElButton>
              <ElButton type="primary" @click="issue(plan)">
                {{ departmentCode === 'finished' ? '确认转入订单' : '确认本次出库' }}
              </ElButton>
            </div>
          </div>
          <ElTable :data="plan.items" border>
            <ElTableColumn prop="item_code" label="编号" min-width="130" />
            <ElTableColumn prop="item_name" label="名称" min-width="180" />
            <ElTableColumn prop="reserved_quantity" label="占用" width="90" />
            <ElTableColumn
              prop="issued_quantity"
              :label="departmentCode === 'finished' ? '已转入' : '已出库'"
              width="90"
            />
            <ElTableColumn
              :label="departmentCode === 'finished' ? '本次转入' : '本次出库'"
              width="150"
            >
              <template #default="{ row }"><ElInputNumber v-model="row.issue_quantity" :min="0" :max="row.remaining_quantity" :controls="false" /></template>
            </ElTableColumn>
          </ElTable>
        </section>
      </ElTabPane>
      <ElTabPane :label="stockTabLabel">
        <ElTable :data="stocks" border stripe><ElTableColumn label="类型" width="100"><template #default="{ row }">{{ itemTypeLabels[row.item_type as keyof typeof itemTypeLabels] }}</template></ElTableColumn><ElTableColumn prop="item_code" label="编号" /><ElTableColumn prop="item_name" label="名称" /><ElTableColumn prop="product_version" label="版本" width="80" /><ElTableColumn prop="quantity" label="现存" width="90" /><ElTableColumn prop="reserved_quantity" label="占用" width="90" /><ElTableColumn prop="available_quantity" label="可用" width="90" /></ElTable>
      </ElTabPane>
      <ElTabPane label="库存流水">
        <ElTable :data="transactions" border stripe><ElTableColumn prop="created_at" label="时间" min-width="180" /><ElTableColumn label="类型" width="115"><template #default="{ row }">{{ transactionLabels[row.transaction_type] || row.transaction_type }}</template></ElTableColumn><ElTableColumn label="对象" min-width="210"><template #default="{ row }"><div>{{ row.item_code }} · {{ row.item_name }}</div><small v-if="row.customer_order_no">订单 {{ row.customer_order_no }}</small></template></ElTableColumn><ElTableColumn prop="quantity" label="数量" width="80" /><ElTableColumn prop="quantity_after" label="结存" width="80" /><ElTableColumn prop="reserved_after" label="占用后" width="90" /><ElTableColumn prop="actor_username" label="操作人" width="110" /><ElTableColumn prop="reason" label="说明" min-width="150" /></ElTable>
      </ElTabPane>
    </ElTabs>
  </section>
</template>

<style scoped>
.inventory-page { padding: 24px; }
.plan-title { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.embedded-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.embedded-heading h2 { margin: 0; font-size: 20px; }
.plan-card { margin-bottom: 18px; padding: 16px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); }
.plan-title { margin-bottom: 12px; }
.plan-actions { display: flex; gap: 8px; }
.plan-actions :deep(.el-button) { margin: 0; }
.inventory-page small { color: var(--el-text-color-secondary); }
</style>
