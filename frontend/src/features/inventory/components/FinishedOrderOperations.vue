<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import {
  confirmFinishedShipment,
  queryFinishedShipmentCandidates,
} from '../api/inventory'
import type { FinishedShipmentCandidate } from '../domain/types'

const props = withDefaults(defineProps<{
  showHeader?: boolean
}>(), {
  showHeader: true,
})
const emit = defineEmits<{ updated: [] }>()
const loading = ref(false)
const rows = ref<FinishedShipmentCandidate[]>([])
const visibleRows = computed(() => rows.value.filter((row) => (
  row.order_status === 'planned' && row.available_quantity > 0 && row.outstanding_quantity > 0
)))

async function load() {
  loading.value = true
  try {
    rows.value = await queryFinishedShipmentCandidates()
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '可发货订单加载失败')
  } finally {
    loading.value = false
  }
}

async function ship(row: FinishedShipmentCandidate) {
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
    await confirmFinishedShipment(row.customer_order_item_id, quantity)
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
      description="按客户订单登记实际发货。"
      @refresh="load"
    />
    <div v-else class="embedded-heading">
      <div>
        <h2>订单发货</h2>
        <p>按客户订单登记成品实际发货数量。</p>
      </div>
      <ElButton @click="load">刷新</ElButton>
    </div>
    <ElTable
      v-table-column-widths="'finished.order-operations'"
      v-loading="loading"
      :data="visibleRows"
      border
      stripe
      table-layout="auto"
      empty-text="暂无可发货订单"
    >
      <ElTableColumn prop="customer_order_no" label="订单编号" min-width="150" />
      <ElTableColumn prop="item_code" label="成品编号" min-width="130" />
      <ElTableColumn prop="item_name" label="成品名称" min-width="160" />
      <ElTableColumn prop="product_version" label="版本" width="80" align="center" />
      <ElTableColumn prop="required_quantity" label="订单需求" width="95" align="right" />
      <ElTableColumn prop="reserved_quantity" label="本计划占用" width="105" align="right" />
      <ElTableColumn prop="unreserved_quantity" label="未占用库存" width="105" align="right" />
      <ElTableColumn prop="available_quantity" label="可发货" width="90" align="right" />
      <ElTableColumn prop="shipped_quantity" label="已发货" width="90" align="right" />
      <ElTableColumn prop="outstanding_quantity" label="尚需发货" width="100" align="right" />
      <ElTableColumn label="操作" width="110" fixed="right">
        <template #default="{ row }">
          <ElButton
            v-if="row.available_quantity && row.outstanding_quantity"
            link
            type="success"
            @click="ship(row)"
          >
            确认发货
          </ElButton>
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
