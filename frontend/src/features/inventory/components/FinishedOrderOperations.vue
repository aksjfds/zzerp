<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '@/features/production/components/DepartmentPageHeader.vue'
import {
  queryFinishedOrderStocks,
  receiveFinishedOrderStock,
  shipFinishedOrderStock,
} from '../api/inventory'
import type { FinishedOrderStock } from '../domain/types'

const props = withDefaults(defineProps<{
  showHeader?: boolean
  mode?: 'all' | 'receipt' | 'shipment'
}>(), {
  showHeader: true,
  mode: 'all',
})
const emit = defineEmits<{ updated: [] }>()
const loading = ref(false)
const rows = ref<FinishedOrderStock[]>([])
const visibleRows = computed(() => rows.value.filter((row) => {
  if (props.mode === 'receipt') return row.pending_quantity > 0
  if (props.mode === 'shipment') {
    return row.order_status === 'planned' && row.available_quantity > 0 && row.outstanding_quantity > 0
  }
  return true
}))

async function load() {
  loading.value = true
  try {
    rows.value = await queryFinishedOrderStocks(props.mode)
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '订单成品加载失败')
  } finally {
    loading.value = false
  }
}

async function receive(row: FinishedOrderStock) {
  try {
    await ElMessageBox.confirm(
      `确认订单 ${row.customer_order_no} 的 ${row.item_code} ${row.item_name} 入库 ${row.pending_quantity} 件？`,
      '成品入库确认',
      { type: 'warning' },
    )
    await receiveFinishedOrderStock(row.customer_order_item_id)
    ElMessage.success('成品入库已确认')
    await load()
    emit('updated')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '成品入库失败')
    }
  }
}

async function ship(row: FinishedOrderStock) {
  try {
    const result = await ElMessageBox.prompt(
      `可发货 ${row.available_quantity}，订单尚需 ${row.outstanding_quantity}`,
      `订单 ${row.customer_order_no} 发货`,
      {
        inputValue: String(Math.min(row.available_quantity, row.outstanding_quantity)),
        inputPattern: /^[1-9]\d*$/,
        inputErrorMessage: '请输入大于0的整数',
        confirmButtonText: '确认发货',
        cancelButtonText: '取消',
      },
    )
    const quantity = Number(result.value)
    if (quantity > row.available_quantity || quantity > row.outstanding_quantity) {
      ElMessage.warning('发货数量超过可发货数量或订单剩余需求')
      return
    }
    await shipFinishedOrderStock(row.customer_order_item_id, quantity)
    ElMessage.success('客户订单发货已登记')
    await load()
    emit('updated')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '订单发货失败')
    }
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <section class="finished-page" :class="{ embedded: !props.showHeader }">
    <DepartmentPageHeader
      v-if="props.showHeader"
      department-name="成品部"
      description="确认生产成品入库，并按客户订单登记实际发货。"
      @refresh="load"
    />
    <div v-else class="embedded-heading">
      <div>
        <h2>{{ mode === 'receipt' ? '成品入库' : mode === 'shipment' ? '订单发货' : '订单成品' }}</h2>
        <p>{{ mode === 'receipt' ? '确认生产完成的成品进入成品部。' : mode === 'shipment' ? '按客户订单登记成品实际发货数量。' : '确认成品入库并登记订单发货。' }}</p>
      </div>
      <ElButton @click="load">刷新</ElButton>
    </div>
    <ElTable
      v-loading="loading"
      :data="visibleRows"
      border
      stripe
      table-layout="auto"
      :empty-text="mode === 'receipt' ? '暂无待入库成品' : mode === 'shipment' ? '暂无可发货订单' : '暂无订单成品'"
    >
      <ElTableColumn prop="customer_order_no" label="订单编号" min-width="150" />
      <ElTableColumn prop="item_code" label="成品编号" min-width="130" />
      <ElTableColumn prop="item_name" label="成品名称" min-width="160" />
      <ElTableColumn prop="product_version" label="版本" width="80" align="center" />
      <ElTableColumn prop="required_quantity" label="订单需求" width="95" align="right" />
      <ElTableColumn v-if="mode !== 'shipment'" prop="pending_quantity" label="待入库" width="90" align="right" />
      <ElTableColumn v-if="mode !== 'receipt'" prop="available_quantity" label="可发货" width="90" align="right" />
      <ElTableColumn v-if="mode !== 'receipt'" prop="shipped_quantity" label="已发货" width="90" align="right" />
      <ElTableColumn v-if="mode !== 'receipt'" prop="outstanding_quantity" label="尚需发货" width="100" align="right" />
      <ElTableColumn label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <ElButton v-if="mode !== 'shipment' && row.pending_quantity" link type="primary" @click="receive(row)">确认入库</ElButton>
          <ElButton v-if="mode !== 'receipt' && row.available_quantity && row.outstanding_quantity" link type="success" @click="ship(row)">确认发货</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>
  </section>
</template>

<style scoped>
.finished-page { padding: 24px; }
.finished-page.embedded { padding: 0; }
.embedded-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.embedded-heading h2 { margin: 0; font-size: 18px; }
.embedded-heading p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
</style>
