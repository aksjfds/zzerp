<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  queryCustomerOrderProduction,
  queryCustomerOrderProgressDetails,
} from '../api/customerOrders'
import type {
  CustomerOrderProgressDetail,
  CustomerOrderProduction,
} from '../domain/types'
import {
  buildOrderProgressRows,
  orderProgressStatusPresentation,
  type OrderProgressMaterialRow,
  type OrderProgressPositionRow,
  type OrderProgressProductRow,
  type OrderProgressTreeRow,
} from '../domain/orderProgressTree'
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
const treeRows = computed(() => buildOrderProgressRows(rows.value))

function isProduct(row: OrderProgressTreeRow): row is OrderProgressProductRow {
  return row.row_type === 'product'
}

function isMaterial(row: OrderProgressTreeRow): row is OrderProgressMaterialRow {
  return row.row_type === 'material'
}

function isPosition(row: OrderProgressTreeRow): row is OrderProgressPositionRow {
  return row.row_type === 'position'
}

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
        <h2>产品生产进度</h2>
        <p>按产品、物料、所在位置三级展示；加工情况标注在对应位置。</p>
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
      :data="treeRows"
      row-key="row_key"
      border
      stripe
      table-layout="auto"
    >
      <ElTableColumn label="产品 / 物料 / 所在位置" min-width="320" class-name="wrap-column">
        <template #default="{ row }">
          <div v-if="isProduct(row)" class="product-cell">
            <ElButton link type="primary" class="product-link" @click="viewProductionFlow(row.product)">
              <span class="directory-icon folder-icon" aria-hidden="true" />
              {{ row.product.product_name }}
            </ElButton>
            <ElTag v-if="!row.product.materials.length" type="info" effect="plain" size="small">
              暂无生产计划物料
            </ElTag>
          </div>
          <div
            v-else-if="isMaterial(row)"
            class="material-cell"
            :class="{ 'is-last': row.is_last_material }"
          >
            <span class="directory-icon material-icon" aria-hidden="true" />
            <span>{{ row.material.item_name }}</span>
            <ElTag :type="row.material.item_type === 'assembly' ? 'warning' : 'info'" effect="plain" size="small">
              {{ row.material.item_type === 'assembly' ? '装配体' : '配件' }}
            </ElTag>
          </div>
          <div
            v-else-if="isPosition(row)"
            class="position-cell"
            :class="{
              'last-material': row.is_last_material,
              'last-position': row.is_last_position,
            }"
          >
            <span class="directory-icon file-icon" aria-hidden="true" />
            <span class="position-name">{{ row.position.position_name }}</span>
            <ElTag
              v-for="(status, statusIndex) in row.position.statuses"
              :key="`${status.status}:${status.status_label}:${statusIndex}`"
              :type="orderProgressStatusPresentation[status.status].type"
              :class="`progress-status-${status.status}`"
              effect="light"
              size="small"
            >
              {{ status.status_label }} · {{ status.quantity }}
            </ElTag>
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn label="编号" min-width="125" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="isProduct(row)">{{ row.product.factory_code }}</span>
          <span v-else-if="isMaterial(row)">{{ row.material.item_code }}</span>
          <span v-else>—</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="订单日期" min-width="96">
        <template #default="{ row }">{{ isProduct(row) ? row.product.order_date : '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="订单号" min-width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ isProduct(row) ? row.product.customer_order_no : '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="客编" min-width="90" show-overflow-tooltip>
        <template #default="{ row }">{{ isProduct(row) ? row.product.customer_code : '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="订单数" min-width="72" align="right">
        <template #default="{ row }">{{ isProduct(row) ? row.product.order_quantity : '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="任务数" min-width="72" align="right">
        <template #default="{ row }">
          <span v-if="isProduct(row)">{{ row.product.task_quantity }}</span>
          <span v-else-if="isMaterial(row)">{{ row.material.task_quantity }}</span>
          <span v-else>—</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="出货数" min-width="72" align="right">
        <template #default="{ row }">{{ isProduct(row) ? row.product.shipped_quantity : '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="欠货数" min-width="72" align="right">
        <template #default="{ row }">
          <span
            v-if="isProduct(row)"
            :class="{ shortage: row.product.outstanding_quantity > 0 }"
          >{{ row.product.outstanding_quantity }}</span>
          <span v-else>—</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="交货日期" min-width="96">
        <template #default="{ row }">{{ isProduct(row) ? row.product.delivery_date : '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="备注" min-width="150" class-name="wrap-column">
        <template #default="{ row }">{{ isProduct(row) ? (row.product.remark || '—') : '—' }}</template>
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
.product-link :deep(span) { display: inline-flex; align-items: center; gap: 8px; }
.product-cell { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; }
.material-cell,
.position-cell { position: relative; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-height: 28px; }
.material-cell { padding-left: 30px; }
.material-cell::before {
  position: absolute;
  top: -24px;
  bottom: 50%;
  left: 8px;
  width: 15px;
  border-bottom: 1px solid var(--md-outline-variant);
  border-left: 1px solid var(--md-outline-variant);
  content: '';
}
.material-cell:not(.is-last)::after {
  position: absolute;
  top: 14px;
  bottom: -24px;
  left: 8px;
  border-left: 1px solid var(--md-outline-variant);
  content: '';
}
.position-cell { padding-left: 60px; }
.position-name { color: var(--el-text-color-regular); font-weight: 600; }
.position-cell::before {
  position: absolute;
  top: -24px;
  bottom: 50%;
  left: 38px;
  width: 15px;
  border-bottom: 1px solid var(--md-outline-variant);
  border-left: 1px solid var(--md-outline-variant);
  content: '';
}
.position-cell:not(.last-position)::after {
  position: absolute;
  top: 14px;
  bottom: -24px;
  left: 38px;
  border-left: 1px solid var(--md-outline-variant);
  content: '';
}
.position-cell:not(.last-material) {
  background: linear-gradient(var(--md-outline-variant), var(--md-outline-variant)) 8px 0 / 1px 100% no-repeat;
}
.progress-status-submitted_qc {
  --el-tag-bg-color: #f3e8ff;
  --el-tag-border-color: #c084fc;
  --el-tag-text-color: #7e22ce;
}
.directory-icon { position: relative; display: inline-block; flex: 0 0 auto; box-sizing: border-box; color: var(--el-color-primary); }
.folder-icon { width: 17px; height: 13px; margin-top: 2px; border: 1.5px solid currentcolor; border-radius: 2px; }
.folder-icon::before { position: absolute; top: -5px; left: -1.5px; width: 8px; height: 5px; border: 1.5px solid currentcolor; border-bottom: 0; border-radius: 2px 2px 0 0; content: ''; }
.material-icon { width: 15px; height: 15px; border: 1.5px solid currentcolor; border-radius: 3px; }
.file-icon { width: 13px; height: 16px; border: 1.5px solid var(--md-outline); border-radius: 2px; }
.file-icon::after { position: absolute; top: 2px; right: 2px; width: 4px; height: 4px; border-top: 1px solid var(--md-outline); border-right: 1px solid var(--md-outline); content: ''; }
.flow-dialog-content { min-height: 240px; }
.progress-details :deep(.wrap-column .cell) { white-space: normal; overflow-wrap: anywhere; line-height: 1.4; }
.pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 680px) {
  .table-heading { align-items: stretch; flex-direction: column; gap: 12px; }
  .customer-filter { width: 100%; }
}
</style>
