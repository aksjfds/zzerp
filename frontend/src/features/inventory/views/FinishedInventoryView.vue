<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import FinishedOrderOperations from '../components/FinishedOrderOperations.vue'
import FinishedInboundOperations from '../components/FinishedInboundOperations.vue'
import {
  queryFinishedStocks,
  queryFinishedStockTransactions,
  reverseFinishedReceipt,
  reverseFinishedShipment,
} from '../api/inventory'
import type {
  FinishedStock,
  FinishedStockTransaction,
} from '../domain/types'

const loading = ref(false)
const stocks = ref<FinishedStock[]>([])
const transactions = ref<FinishedStockTransaction[]>([])
const finishedInboundOperations = ref<InstanceType<typeof FinishedInboundOperations>>()
const finishedShipmentOperations = ref<InstanceType<typeof FinishedOrderOperations>>()
const transactionLabels: Record<string, string> = {
  receipt: '成品入库',
  customer_shipment: '客户发货',
  receipt_reversal: '入库冲销',
  customer_shipment_reversal: '发货冲销',
}
const reversedTransactionIds = computed(() => new Set(
  transactions.value
    .map(item => item.reversal_of_transaction_id)
    .filter((id): id is number => id !== null),
))

function canReverse(row: FinishedStockTransaction) {
  return (
    (row.transaction_type === 'receipt' || row.transaction_type === 'customer_shipment')
    && !reversedTransactionIds.value.has(row.id)
  )
}

async function reverseTransaction(row: FinishedStockTransaction) {
  try {
    await ElMessageBox.confirm(
      row.transaction_type === 'receipt'
        ? '仅该批成品仍有足够未占用库存时可以冲销入库。'
        : '仅该订单产品最新且未冲销的发货记录可以冲销。库存、占用和订单状态会同时恢复。',
      row.transaction_type === 'receipt' ? '冲销成品入库' : '冲销客户发货',
      { type: 'warning', confirmButtonText: '确认冲销', cancelButtonText: '取消' },
    )
    if (row.transaction_type === 'receipt') {
      if (!row.finished_receipt_id) return
      await reverseFinishedReceipt(row.finished_receipt_id)
    } else {
      await reverseFinishedShipment(row.id)
    }
    await refreshFinishedOperations()
    ElMessage.success('库存业务已冲销')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '库存业务冲销失败')
    }
  }
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
    finishedInboundOperations.value?.load(),
    finishedShipmentOperations.value?.load(),
  ])
}

async function refreshAfterInbound() {
  await Promise.all([
    load(),
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
      @refresh="refreshFinishedOperations"
    />
    <ElTabs>
      <ElTabPane label="成品入库">
        <FinishedInboundOperations
          ref="finishedInboundOperations"
          @updated="refreshAfterInbound"
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
          <ElTableColumn label="操作" width="90" fixed="right">
            <template #default="{ row }">
              <ElButton
                v-if="canReverse(row)"
                link
                type="danger"
                @click="reverseTransaction(row)"
              >冲销</ElButton>
              <span v-else>—</span>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>
    </ElTabs>
  </section>
</template>

<style scoped>
.inventory-page { padding: 24px; }
.inventory-page small { color: var(--el-text-color-secondary); }
</style>
