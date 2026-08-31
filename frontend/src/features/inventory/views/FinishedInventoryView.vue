<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import FinishedOrderOperations from '../components/FinishedOrderOperations.vue'
import FinishedReceiptOperations from '../components/FinishedReceiptOperations.vue'
import {
  queryFinishedStocks,
  queryFinishedStockTransactions,
} from '../api/inventory'
import type {
  FinishedStock,
  FinishedStockTransaction,
} from '../domain/types'

const loading = ref(false)
const stocks = ref<FinishedStock[]>([])
const transactions = ref<FinishedStockTransaction[]>([])
const finishedReceiptOperations = ref<InstanceType<typeof FinishedReceiptOperations>>()
const finishedShipmentOperations = ref<InstanceType<typeof FinishedOrderOperations>>()
const transactionLabels: Record<string, string> = {
  receipt: '成品入库',
  customer_shipment: '客户发货',
}

async function load() {
  loading.value = true
  try {
    const [nextStocks, nextTransactions] = await Promise.all([
      queryFinishedStocks(),
      queryFinishedStockTransactions(),
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
      description="确认待入库成品、管理统一成品库存，并按客户订单办理发货。"
      @refresh="load"
    />
    <ElTabs>
      <ElTabPane label="待入库">
        <FinishedReceiptOperations
          ref="finishedReceiptOperations"
          @updated="refreshFinishedOperations"
        />
      </ElTabPane>
      <ElTabPane label="成品库存">
        <ElTable
          v-table-column-widths="'finished.stocks'"
          :data="stocks"
          border
          stripe
          table-layout="auto"
          empty-text="暂无成品库存"
        >
          <ElTableColumn prop="item_code" label="编号" min-width="150" />
          <ElTableColumn prop="item_name" label="名称" min-width="180" />
          <ElTableColumn prop="product_version" label="版本" width="80" />
          <ElTableColumn prop="quantity" label="现存" width="90" align="right" />
          <ElTableColumn prop="reserved_quantity" label="占用" width="90" align="right" />
          <ElTableColumn prop="available_quantity" label="可用" width="90" align="right" />
        </ElTable>
      </ElTabPane>
      <ElTabPane label="客户订单发货">
        <FinishedOrderOperations
          ref="finishedShipmentOperations"
          :show-header="false"
          @updated="refreshFinishedOperations"
        />
      </ElTabPane>
      <ElTabPane label="库存流水">
        <ElTable
          v-table-column-widths="'finished.transactions'"
          :data="transactions"
          border
          stripe
          table-layout="auto"
          empty-text="暂无库存流水"
        >
          <ElTableColumn prop="created_at" label="时间" min-width="180" />
          <ElTableColumn label="类型" min-width="120">
            <template #default="{ row }">
              {{ transactionLabels[row.transaction_type] || row.transaction_type }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="对象" min-width="240">
            <template #default="{ row }">
              <div>{{ row.item_code }} · {{ row.item_name }}</div>
              <small v-if="row.customer_order_no">
                订单 {{ row.customer_order_no }}
              </small>
            </template>
          </ElTableColumn>
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
