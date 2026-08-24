<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  queryCustomerOrderProduction,
  queryCustomerOrderProgressDetails,
} from '../api/customerOrders'
import type {
  CustomerOrderProgressDetail,
  CustomerOrderProduction,
} from '../domain/types'
import { queryCustomers, type Customer } from '@/features/customers'
import { useWorkshopDepartmentCodes } from '@/features/departments'
import ProductionFlowViewer from '@/shared/process-flow/ProductionFlowViewer.vue'

const loading = ref(false)
const rows = ref<CustomerOrderProgressDetail[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const customers = ref<Customer[]>([])
const customerId = ref<number>()
const customerLoading = ref(false)
const flowVisible = ref(false)
const flowLoading = ref(false)
const flowRow = ref<CustomerOrderProgressDetail>()
const flowProduct = ref<CustomerOrderProduction['products'][number]>()
const { workshopDepartmentCodes } = useWorkshopDepartmentCodes()

async function viewProductionFlow(row: CustomerOrderProgressDetail) {
  flowRow.value = row
  flowProduct.value = undefined
  flowVisible.value = true
  flowLoading.value = true
  try {
    const production = await queryCustomerOrderProduction(row.customer_order_id)
    flowProduct.value = production.products.find(
      item => item.customer_order_item_id === row.customer_order_item_id,
    )
    if (!flowProduct.value) ElMessage.warning('该产品尚未生成生产流程')
  } catch {
    ElMessage.error('生产进度加载失败')
  } finally {
    flowLoading.value = false
  }
}

async function loadCustomers() {
  customerLoading.value = true
  try {
    customers.value = await queryCustomers()
  } finally {
    customerLoading.value = false
  }
}

async function changeCustomer() {
  page.value = 1
  await load()
}

async function load() {
  loading.value = true
  try {
    const result = await queryCustomerOrderProgressDetails(
      page.value,
      pageSize,
      customerId.value,
    )
    rows.value = result.items
    total.value = result.total
  } catch {
    ElMessage.error('进度明细加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => Promise.all([loadCustomers(), load()]))
defineExpose({ load })
</script>

<template>
  <section class="progress-details">
    <div class="table-heading">
      <div>
        <h2>产品订单进度</h2>
        <p>每个订单产品单独一行，出货数量按实际发货流水统计。</p>
      </div>
      <ElSelect
        v-model="customerId"
        class="customer-filter"
        clearable
        :loading="customerLoading"
        placeholder="全部客户"
        @change="changeCustomer"
      >
        <ElOption
          v-for="customer in customers"
          :key="customer.id"
          :label="customer.customer_name"
          :value="customer.id"
        />
      </ElSelect>
    </div>
    <ElTable
      v-table-column-widths="'sales.progress-details'"
      v-loading="loading"
      :data="rows"
      border
      stripe
      table-layout="auto"
    >
      <ElTableColumn prop="factory_code" label="厂编" min-width="90" show-overflow-tooltip />
      <ElTableColumn prop="product_name" label="产品名" min-width="145" class-name="wrap-column">
        <template #default="{ row }">
          <ElButton link type="primary" class="product-link" @click="viewProductionFlow(row)">
            {{ row.product_name }}
          </ElButton>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="order_date" label="订单日期" min-width="96" />
      <ElTableColumn prop="customer_order_no" label="订单号" min-width="110" show-overflow-tooltip />
      <ElTableColumn prop="customer_code" label="客编" min-width="90" show-overflow-tooltip />
      <ElTableColumn prop="order_quantity" label="订单数" min-width="72" align="right" />
      <ElTableColumn prop="task_quantity" label="任务数" min-width="72" align="right" />
      <ElTableColumn prop="shipped_quantity" label="出货数" min-width="72" align="right" />
      <ElTableColumn prop="outstanding_quantity" label="欠货数" min-width="72" align="right">
        <template #default="{ row }">
          <span :class="{ shortage: row.outstanding_quantity > 0 }">{{ row.outstanding_quantity }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="delivery_date" label="交货日期" min-width="96" />
      <ElTableColumn prop="remark" label="备注" min-width="150" class-name="wrap-column">
        <template #default="{ row }">{{ row.remark || '—' }}</template>
      </ElTableColumn>
    </ElTable>
    <ElPagination
      v-model:current-page="page"
      class="pagination"
      layout="prev, pager, next, total"
      :page-size="pageSize"
      :total="total"
      @current-change="load"
    />
    <ElDialog
      v-model="flowVisible"
      :title="flowRow ? `${flowRow.factory_code} · ${flowRow.product_name} 生产进度` : '生产进度'"
      width="min(1400px, 96vw)"
      destroy-on-close
    >
      <div v-loading="flowLoading" class="flow-dialog-content">
        <ProductionFlowViewer
          v-if="flowProduct"
          :flow="flowProduct.process_flow"
          :stats="flowProduct.node_stats"
          :edge-stats="flowProduct.edge_stats"
          :workshop-department-codes="workshopDepartmentCodes"
        />
        <ElEmpty v-else-if="!flowLoading" description="该产品尚未生成生产流程" />
      </div>
      <template #footer><ElButton @click="flowVisible = false">关闭</ElButton></template>
    </ElDialog>
  </section>
</template>

<style scoped>
.progress-details { min-width: 0; }
.table-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.table-heading h2 { margin: 0; font-size: 18px; }
.table-heading p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.customer-filter { width: min(280px, 100%); }
.shortage { color: var(--el-color-danger); font-weight: 600; }
.product-link { height: auto; padding: 0; white-space: normal; text-align: left; line-height: 1.4; }
.flow-dialog-content { min-height: 240px; }
.progress-details :deep(.wrap-column .cell) { white-space: normal; overflow-wrap: anywhere; line-height: 1.4; }
.pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 680px) {
  .table-heading { align-items: stretch; flex-direction: column; gap: 12px; }
  .customer-filter { width: 100%; }
}
</style>
