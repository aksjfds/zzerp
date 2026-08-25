<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import FinishedOrderOperations from '../components/FinishedOrderOperations.vue'
import {
  queryFinishedInventoryStocks,
  queryFinishedInventoryTransactions,
} from '../api/inventory'
import type {
  FinishedInventoryStock,
  FinishedInventoryTransaction,
} from '../domain/types'

const loading = ref(false)
const stocks = ref<FinishedInventoryStock[]>([])
const transactions = ref<FinishedInventoryTransaction[]>([])
const finishedReceiptOperations = ref<InstanceType<typeof FinishedOrderOperations>>()
const finishedShipmentOperations = ref<InstanceType<typeof FinishedOrderOperations>>()
const transactionLabels: Record<string, string> = {
  receipt: '入库', issue: '出库',
  finished_receipt: '成品入库', finished_stock_issue: '库存转入订单',
  finished_surplus_transfer: '订单结余转库存',
  customer_shipment: '客户发货',
}

async function load() {
  loading.value = true
  try {
    const [nextStocks, nextTransactions] = await Promise.all([
      queryFinishedInventoryStocks(),
      queryFinishedInventoryTransactions(),
    ])
    stocks.value = nextStocks
    transactions.value = nextTransactions
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '成品部数据加载失败')
  } finally {
    loading.value = false
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
      department-name="成品部"
      description="办理成品入库和订单发货，并查看成品库存及本项目成品流水。"
      @refresh="load"
    />
    <ElTabs>
      <ElTabPane label="成品入库">
        <FinishedOrderOperations
          ref="finishedReceiptOperations"
          :show-header="false"
          mode="receipt"
          @updated="refreshFinishedOperations"
        />
      </ElTabPane>
      <ElTabPane label="订单发货">
        <FinishedOrderOperations
          ref="finishedShipmentOperations"
          :show-header="false"
          mode="shipment"
          @updated="refreshFinishedOperations"
        />
      </ElTabPane>
      <ElTabPane label="成品库存">
        <ElTable v-table-column-widths="'finished.stocks'" :data="stocks" border stripe table-layout="auto">
          <ElTableColumn prop="item_code" label="编号" min-width="150" />
          <ElTableColumn prop="item_name" label="名称" min-width="180" />
          <ElTableColumn prop="product_version" label="版本" width="80" />
          <ElTableColumn prop="completed_node_label" label="完成状态" min-width="130"><template #default="{ row }">{{ `${row.completed_node_label}完` }}</template></ElTableColumn>
          <ElTableColumn prop="quantity" label="现存" width="90" align="right" />
          <ElTableColumn prop="available_quantity" label="可用" width="90" align="right" />
        </ElTable>
      </ElTabPane>
      <ElTabPane label="本项目成品流水">
        <ElTable v-table-column-widths="'finished.transactions'" :data="transactions" border stripe table-layout="auto">
          <ElTableColumn prop="created_at" label="时间" min-width="180" />
          <ElTableColumn label="类型" min-width="120"><template #default="{ row }">{{ transactionLabels[row.transaction_type] || row.transaction_type }}</template></ElTableColumn>
          <ElTableColumn label="对象" min-width="240"><template #default="{ row }"><div>{{ row.item_code }} · {{ row.item_name }}</div><small v-if="row.completed_node_label">{{ row.completed_node_label }}完</small><small v-if="row.customer_order_no">订单 {{ row.customer_order_no }}</small></template></ElTableColumn>
          <ElTableColumn prop="quantity" label="数量" width="90" align="right" />
          <ElTableColumn prop="quantity_after" label="结存" width="90" align="right" />
          <ElTableColumn prop="actor_username" label="操作人" min-width="110" />
          <ElTableColumn prop="reason" label="说明" min-width="180" show-overflow-tooltip />
        </ElTable>
      </ElTabPane>
    </ElTabs>
  </section>
</template>

<style scoped>
.inventory-page { padding: 24px; }
.inventory-page small { color: var(--el-text-color-secondary); }
</style>
