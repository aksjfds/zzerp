<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { ORDER_PERMISSIONS } from '@/permission/constants'
import ProductionPlanEditor from '../components/ProductionPlanEditor.vue'
import {
  completeProductionPlan,
  confirmProductionPlan,
  queryProductionPlanOrders,
} from '../api/customerOrders'
import type { CustomerOrder, ProductionPlan } from '../domain/types'

type PlanEditorApi = {
  save: (options?: { silent?: boolean }) => Promise<ProductionPlan | undefined>
}

const loading = ref(false)
const orders = ref<CustomerOrder[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const dialogVisible = ref(false)
const activeOrder = ref<CustomerOrder>()
const activePlan = ref<ProductionPlan>()
const editor = ref<PlanEditorApi>()
const confirming = ref(false)
const completing = ref(false)
const savingDraft = ref(false)
const planInvalid = ref(true)

const statusLabels: Record<string, string> = {
  confirmed: '计划待确认',
  planned: '生产中',
  closed: '订单已结单 · 计划继续生产',
}
const statusTypes = {
  confirmed: 'primary',
  planned: 'warning',
  closed: 'warning',
} as const

function orderPlanStatusLabel(order: CustomerOrder) {
  if (order.production_plan_status === 'completed') return '生产计划已完成'
  return statusLabels[order.status] || order.status
}

function orderPlanStatusType(order: CustomerOrder) {
  if (order.production_plan_status === 'completed') return 'success'
  return statusTypes[order.status as keyof typeof statusTypes]
}

async function load() {
  loading.value = true
  try {
    const result = await queryProductionPlanOrders(page.value, pageSize)
    orders.value = result.items
    total.value = result.total
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '生产计划列表加载失败')
  } finally {
    loading.value = false
  }
}

function openPlan(order: CustomerOrder) {
  activeOrder.value = order
  activePlan.value = undefined
  planInvalid.value = true
  dialogVisible.value = true
}

async function saveDraft() {
  savingDraft.value = true
  try {
    await editor.value?.save()
  } finally {
    savingDraft.value = false
  }
}

async function confirmPlan() {
  const order = activeOrder.value
  if (!order || order.status !== 'confirmed') return
  confirming.value = true
  try {
    const saved = await editor.value?.save({ silent: true })
    if (!saved) return
    const deductions = saved.inventory_items.filter(item => item.planned_deduction_quantity > 0)
    const deductionDetails = deductions.length
      ? deductions.map(item => (
          `${item.item_code} / ${item.completed_node_label} / `
          + `${item.warehouse_code} ${item.warehouse_name}：${item.planned_deduction_quantity} 件`
        )).join('；')
      : '本计划不使用现有库存'
    await ElMessageBox.confirm(
      `确认时将再次读取库存并直接扣减，成功后不能取消生产计划。${deductionDetails}。是否继续？`,
      '确认生产计划',
      { type: 'warning' },
    )
    await confirmProductionPlan(order.id, order.revision, saved.revision)
    ElMessage.success('生产计划已确认并进入生产')
    dialogVisible.value = false
    await load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '生产计划确认失败')
    }
  } finally {
    confirming.value = false
  }
}

async function completePlan() {
  const order = activeOrder.value
  const plan = activePlan.value
  if (!order || !plan || plan.status !== 'confirmed') return
  try {
    await ElMessageBox.confirm(
      '完成仅更新生产计划的管理状态，现有工单和后续开单仍可继续，且计划不能取消。是否继续？',
      '完成生产计划',
      { type: 'warning', confirmButtonText: '确认完成' },
    )
    completing.value = true
    activePlan.value = await completeProductionPlan(order.id, plan.revision)
    ElMessage.success('生产计划已完成')
    await load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '生产计划完成失败')
    }
  } finally {
    completing.value = false
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <section class="plans-view">
    <div class="plans-heading">
      <div>
        <h2>生产计划</h2>
        <p>客户订单确认后自动生成草稿计划；客户订单结单后，已确认生产计划仍会继续生产。</p>
      </div>
      <ElButton :loading="loading" @click="load">刷新</ElButton>
    </div>
    <ElTable v-table-column-widths="'sales.production-plans'" v-loading="loading" :data="orders" border stripe table-layout="auto">
      <ElTableColumn prop="customer_order_no" label="订单编号" min-width="150" />
      <ElTableColumn prop="customer_name" label="客户名称" min-width="150" />
      <ElTableColumn label="产品" min-width="260">
        <template #default="{ row }">
          <div v-for="item in row.items" :key="item.id">
            {{ item.factory_code }} · {{ item.product_name }} · {{ item.quantity }}个
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn label="状态" min-width="200">
        <template #default="{ row }">
          <ElTag :type="orderPlanStatusType(row)" effect="light">
            {{ orderPlanStatusLabel(row) }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="updated_at" label="更新时间" width="170" />
      <ElTableColumn label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <ElButton link type="primary" @click="openPlan(row)">
            {{ row.status === 'confirmed' ? '填写计划' : '查看计划' }}
          </ElButton>
        </template>
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
      v-model="dialogVisible"
      :title="`生产计划 · ${activeOrder?.customer_order_no || ''}`"
      width="min(1380px, 96vw)"
      destroy-on-close
    >
      <ProductionPlanEditor
        v-if="activeOrder"
        ref="editor"
        :order-id="activeOrder.id"
        :editable="activeOrder.status === 'confirmed'"
        @updated="activePlan = $event"
        @validity-change="planInvalid = $event"
      />
      <template #footer>
        <div class="dialog-actions">
          <ElButton
            :disabled="savingDraft || confirming || completing"
            @click="dialogVisible = false"
          >关闭</ElButton>
          <div v-if="activeOrder?.status === 'confirmed'" class="dialog-primary-actions">
            <ElButton
              v-permission="ORDER_PERMISSIONS.edit"
              :loading="savingDraft"
              :disabled="planInvalid || confirming"
              @click="saveDraft"
            >暂存计划</ElButton>
            <ElButton
              v-permission="ORDER_PERMISSIONS.confirm"
              type="primary"
              :loading="confirming"
              :disabled="!activePlan || planInvalid || savingDraft"
              @click="confirmPlan"
            >保存并确认</ElButton>
          </div>
          <ElButton
            v-else-if="activePlan?.status === 'confirmed'"
            v-permission="ORDER_PERMISSIONS.confirm"
            type="success"
            :loading="completing"
            @click="completePlan"
          >完成生产计划</ElButton>
        </div>
      </template>
    </ElDialog>
  </section>
</template>

<style scoped>
.plans-view { min-width: 0; }
.plans-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.plans-heading h2 { margin: 0; font-size: 20px; }
.plans-heading p { margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.dialog-actions { display: flex; justify-content: space-between; align-items: center; gap: 12px; width: 100%; }
.dialog-primary-actions { display: flex; align-items: center; gap: 10px; }
.dialog-actions :deep(.el-button) { margin-left: 0; }
.pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 680px) {
  .plans-heading { align-items: stretch; flex-direction: column; }
  .dialog-actions { align-items: stretch; flex-direction: column-reverse; }
  .dialog-primary-actions { display: grid; grid-template-columns: 1fr 1fr; }
  .dialog-actions :deep(.el-button) { width: 100%; }
}
</style>
