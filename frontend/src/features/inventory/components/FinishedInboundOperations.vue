<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryFinishedInboundItems, receiveFinishedReceipt } from '../api/inventory'
import type { FinishedInboundItem, PendingFinishedReceipt } from '../domain/types'

const emit = defineEmits<{ updated: [] }>()
const loading = ref(false)
const rows = ref<FinishedInboundItem[]>([])
const page = ref(1)
const pageSize = 50
const total = ref(0)

async function loadPage(targetPage: number) {
  const result = await queryFinishedInboundItems(targetPage, pageSize)
  rows.value = result.data
  total.value = result.total
}

async function load() {
  loading.value = true
  try {
    await loadPage(page.value)
    const lastPage = Math.max(Math.ceil(total.value / pageSize), 1)
    if (page.value > lastPage) {
      page.value = lastPage
      await loadPage(page.value)
    }
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '成品入库数据加载失败')
  } finally {
    loading.value = false
  }
}

function rowKey(row: FinishedInboundItem) {
  return `${row.product_id}:${row.product_version}`
}

function statusPresentation(row: FinishedInboundItem) {
  if (row.pending_receipts.length > 0) {
    return { label: `待确认入库 · ${row.pending_receipts.length} 批`, type: 'warning' as const }
  }
  if (row.planned_quantity <= 0) {
    return { label: '无需生产', type: 'info' as const }
  }
  if (row.arrived_quantity >= row.planned_quantity) {
    return { label: '已到齐', type: 'success' as const }
  }
  if (row.arrived_quantity > 0) {
    return { label: '部分到货', type: 'primary' as const }
  }
  return { label: '未到货', type: 'info' as const }
}

function receiptSource(receipt: PendingFinishedReceipt) {
  return receipt.work_order_batch_id
    ? `QC批次 #${receipt.work_order_batch_id}`
    : `装包工单 #${receipt.work_order_id}`
}

async function receive(row: FinishedInboundItem, receipt: PendingFinishedReceipt) {
  try {
    await ElMessageBox.confirm(
      `确认将 ${row.item_code} ${row.item_name}（版本 ${row.product_version}）整批 ${receipt.quantity} PCS 入库？`,
      '成品整批入库',
      { type: 'warning', confirmButtonText: '确认入库', cancelButtonText: '取消' },
    )
    await receiveFinishedReceipt(receipt.id)
    ElMessage.success('成品已整批入库')
    await load()
    emit('updated')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '成品入库失败')
    }
  }
}

function changePage(nextPage: number) {
  page.value = nextPage
  void load()
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <section>
    <ElTable
      v-table-column-widths="'finished.inbound'"
      v-loading="loading"
      :data="rows"
      :row-key="rowKey"
      border
      stripe
      table-layout="auto"
      empty-text="暂无成品入库信息"
    >
      <ElTableColumn label="成品" min-width="260">
        <template #default="{ row }">{{ row.item_code }} · {{ row.item_name }}</template>
      </ElTableColumn>
      <ElTableColumn label="状态" min-width="160">
        <template #default="{ row }">
          <ElTag :type="statusPresentation(row).type" effect="plain">
            {{ statusPresentation(row).label }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="planned_quantity" label="计划数量" min-width="110" align="right" />
      <ElTableColumn prop="arrived_quantity" label="到货数" min-width="100" align="right" />
      <ElTableColumn label="操作" min-width="130" fixed="right">
        <template #default="{ row }">
          <ElButton
            v-if="row.pending_receipts.length === 1"
            link
            type="primary"
            @click="receive(row, row.pending_receipts[0])"
          >
            确认入库
          </ElButton>
          <ElPopover
            v-else-if="row.pending_receipts.length > 1"
            placement="left"
            :width="320"
            trigger="click"
          >
            <template #reference>
              <ElButton link type="primary">选择入库批次</ElButton>
            </template>
            <div class="receipt-list">
              <div
                v-for="receipt in row.pending_receipts"
                :key="receipt.id"
                class="receipt-item"
              >
                <div>
                  <strong>{{ receipt.quantity }} PCS</strong>
                  <small>{{ receiptSource(receipt) }} · {{ receipt.created_at }}</small>
                </div>
                <ElButton size="small" type="primary" @click="receive(row, receipt)">
                  入库
                </ElButton>
              </div>
            </div>
          </ElPopover>
          <span v-else>—</span>
        </template>
      </ElTableColumn>
    </ElTable>
    <ElPagination
      v-if="total > pageSize"
      class="pagination"
      background
      layout="prev, pager, next, total"
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      @current-change="changePage"
    />
  </section>
</template>

<style scoped>
.pagination { justify-content: flex-end; margin-top: 16px; }
.receipt-list { display: grid; gap: 10px; }
.receipt-item { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.receipt-item div { min-width: 0; }
.receipt-item small { display: block; margin-top: 3px; color: var(--el-text-color-secondary); }
</style>
