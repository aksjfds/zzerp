<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { ORDER_PERMISSIONS } from '@/permission/constants'
import ProductionPlanEditor from '../components/ProductionPlanEditor.vue'
import {
  confirmProductionPlan,
  queryProductionPlanOrders,
} from '../api/customerOrders'
import type { CustomerOrder, ProductionPlan } from '../domain/types'

type PlanEditorApi = {
  save: () => Promise<ProductionPlan | undefined>
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
const savingDraft = ref(false)
const planInvalid = ref(true)

const statusLabels: Record<string, string> = {
  confirmed: '计划待确认',
  planned: '生产中',
  closed: '已结单',
}
const statusTypes = {
  confirmed: 'primary',
  planned: 'warning',
  closed: 'success',
} as const

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
  try {
    await ElMessageBox.confirm(
      '确认生产计划后，系统会重新核算并占用库存，同时初始化生产流程。是否继续？',
      '确认生产计划',
      { type: 'warning' },
    )
    confirming.value = true
    const saved = await editor.value?.save()
    if (!saved) return
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

onMounted(load)
defineExpose({ load })
</script>

<template>
  <section class="plans-view">
    <div class="plans-heading">
      <div>
        <h2>生产计划</h2>
        <p>客户订单确认后自动生成草稿计划；确认计划时才占用库存并开始生产。</p>
      </div>
      <ElButton @click="load">刷新</ElButton>
    </div>
    <ElTable v-loading="loading" :data="orders" border stripe>
      <ElTableColumn prop="customer_order_no" label="订单编号" min-width="150" />
      <ElTableColumn prop="customer_name" label="客户名称" min-width="150" />
      <ElTableColumn label="产品" min-width="260">
        <template #default="{ row }">
          <div v-for="item in row.items" :key="item.id">
            {{ item.factory_code }} · {{ item.product_name }} · {{ item.quantity }}个
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn label="状态" width="120">
        <template #default="{ row }">
          <ElTag :type="statusTypes[row.status as keyof typeof statusTypes]" effect="light">
            {{ statusLabels[row.status] || row.status }}
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
        <ElButton
          :disabled="savingDraft || confirming"
          @click="dialogVisible = false"
        >{{ activeOrder?.status === 'confirmed' ? '取消' : '关闭' }}</ElButton>
        <ElButton
          v-if="activeOrder?.status === 'confirmed'"
          v-permission="ORDER_PERMISSIONS.edit"
          :loading="savingDraft"
          :disabled="planInvalid || confirming"
          @click="saveDraft"
        >保存草稿</ElButton>
        <ElButton
          v-if="activeOrder?.status === 'confirmed'"
          v-permission="ORDER_PERMISSIONS.confirm"
          type="primary"
          :loading="confirming"
          :disabled="!activePlan || planInvalid || savingDraft"
          @click="confirmPlan"
        >确认生产计划</ElButton>
      </template>
    </ElDialog>
  </section>
</template>

<style scoped>
.plans-view { min-width: 0; }
.plans-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.plans-heading h2 { margin: 0; font-size: 20px; }
.plans-heading p { margin: 5px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 680px) {
  .plans-heading { align-items: stretch; flex-direction: column; }
}
</style>
