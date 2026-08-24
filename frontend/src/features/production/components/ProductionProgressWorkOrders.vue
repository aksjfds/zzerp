<script setup lang="ts">
import type { ProductionProgressWorkOrder } from '../domain/productionProgress'
import { workOrderStatusLabel } from '../domain/workOrderStatus'

defineProps<{ workOrders: ProductionProgressWorkOrder[] }>()

function displayWorkOrderStatus(row: ProductionProgressWorkOrder) {
  return workOrderStatusLabel(row.status)
}
</script>

<template>
  <ElCollapse v-if="workOrders.length" class="work-order-collapse">
    <ElCollapseItem :title="`查看工单明细（${workOrders.length}）`">
      <ElTable v-table-column-widths="'production.progress-work-orders'" :data="workOrders" border table-layout="auto" size="small">
        <ElTableColumn prop="work_order_no" label="工单号" min-width="150" />
        <ElTableColumn label="工人/公司" min-width="110">
          <template #default="{ row }">{{ row.worker_name || '—' }}</template>
        </ElTableColumn>
        <ElTableColumn prop="quantity" label="工单数" min-width="80" align="right" />
        <ElTableColumn prop="processed_quantity" label="加工数" min-width="80" align="right" />
        <ElTableColumn prop="submitted_quantity" label="送检数" min-width="80" align="right" />
        <ElTableColumn prop="pending_qc_quantity" label="待检数" min-width="80" align="right" />
        <ElTableColumn prop="completed_quantity" label="完成数" min-width="80" align="right" />
        <ElTableColumn prop="rework_quantity" label="返工" min-width="70" align="right" />
        <ElTableColumn prop="scrap_quantity" label="报废" min-width="70" align="right" />
        <ElTableColumn prop="lost_quantity" label="丢失" min-width="70" align="right" />
        <ElTableColumn label="状态" min-width="80">
          <template #default="{ row }">{{ displayWorkOrderStatus(row) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="created_at" label="创建时间" min-width="150" />
        <ElTableColumn label="完成时间" min-width="150">
          <template #default="{ row }">{{ row.closed_at || '—' }}</template>
        </ElTableColumn>
      </ElTable>
    </ElCollapseItem>
  </ElCollapse>
  <p v-else class="no-work-order">尚未创建工单</p>
</template>

<style scoped>
.work-order-collapse { margin-top: 12px; }
.no-work-order { margin: 16px 0 0; color: var(--md-on-surface-variant); text-align: center; font-size: 13px; }
</style>
