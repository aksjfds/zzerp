<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryFinishedReceipts, receiveFinishedReceipt } from '../api/inventory'
import type { FinishedReceipt } from '../domain/types'

const emit = defineEmits<{ updated: [] }>()
const loading = ref(false)
const rows = ref<FinishedReceipt[]>([])

async function load() {
  loading.value = true
  try {
    rows.value = await queryFinishedReceipts()
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '待入库成品加载失败')
  } finally {
    loading.value = false
  }
}

async function receive(row: FinishedReceipt) {
  try {
    await ElMessageBox.confirm(
      `确认将 ${row.item_code} ${row.item_name}（版本 ${row.product_version}）整批 ${row.quantity} PCS 入库？`,
      '成品整批入库',
      { type: 'warning', confirmButtonText: '确认入库', cancelButtonText: '取消' },
    )
    await receiveFinishedReceipt(row.id)
    ElMessage.success('成品已整批入库')
    await load()
    emit('updated')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '成品入库失败')
    }
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <section>
    <div class="embedded-heading">
      <div>
        <h2>待入库</h2>
        <p>QC 放行或装包完成后的成品按批次整批确认入库。</p>
      </div>
      <ElButton @click="load">刷新</ElButton>
    </div>
    <ElTable
      v-table-column-widths="'finished.receipts'"
      v-loading="loading"
      :data="rows"
      border
      stripe
      table-layout="auto"
      empty-text="暂无待入库成品"
    >
      <ElTableColumn prop="item_code" label="成品编号" min-width="140" />
      <ElTableColumn prop="item_name" label="成品名称" min-width="180" />
      <ElTableColumn prop="product_version" label="版本" width="80" align="center" />
      <ElTableColumn label="来源" min-width="140">
        <template #default="{ row }">
          {{ row.work_order_batch_id ? `QC批次 #${row.work_order_batch_id}` : `装包工单 #${row.work_order_id}` }}
        </template>
      </ElTableColumn>
      <ElTableColumn prop="quantity" label="整批数量" width="100" align="right" />
      <ElTableColumn prop="created_at" label="待入库时间" min-width="180" />
      <ElTableColumn label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <ElButton link type="primary" @click="receive(row)">确认入库</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>
  </section>
</template>

<style scoped>
.embedded-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.embedded-heading h2 { margin: 0; font-size: 18px; }
.embedded-heading p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
</style>
