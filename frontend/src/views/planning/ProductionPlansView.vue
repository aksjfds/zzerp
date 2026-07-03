<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { queryV2CustomerOrders } from '@/api/customerOrders'
import {
  cancelV2ProductionPlan,
  createV2ProductionPlan,
  previewV2ProductionPlan,
  previewV2ProductionPlanUpdate,
  queryV2ProductionPlans,
  releaseV2ProductionPlan,
  updateV2ProductionPlan,
} from '@/api/productionPlans'
import type { CustomerOrder } from '@/types/sales'
import type {
  PlanItemInput,
  ProductionPlan,
  ProductionPlanPreview,
  ProductionPlanStatus,
} from '@/types/planning'

type SelectableItem = {
  id: number
  selected: boolean
  plannedFinishedQuantity: number
}

const loading = ref(false)
const router = useRouter()
const authStore = useAuthStore()
const plans = ref<ProductionPlan[]>([])
const orders = ref<CustomerOrder[]>([])
const statusFilter = ref<ProductionPlanStatus>()
const dialogVisible = ref(false)
const editingPlanId = ref<number>()
const preview = ref<ProductionPlanPreview>()
const previewSignature = ref('')
const form = reactive({
  customerOrderId: undefined as number | undefined,
  startDate: '',
  completionDate: '',
  items: [] as SelectableItem[],
})

const statusLabels: Record<ProductionPlanStatus, string> = {
  draft: '草稿',
  released: '已下达',
  producing: '生产中',
  completed: '已完成',
  cancelled: '已取消',
}
const displayedPlans = computed(() => statusFilter.value
  ? plans.value.filter((item) => item.status === statusFilter.value)
  : plans.value)
const availableOrders = computed(() => orders.value.filter(
  (item) => ['confirmed', 'planned'].includes(item.status),
))
const activeOrder = computed(() => orders.value.find(
  (item) => item.id === form.customerOrderId,
))
const usedOrderItemIds = computed(() => new Set(
  plans.value.filter(
    (plan) => plan.status !== 'cancelled' && plan.id !== editingPlanId.value,
  ).flatMap((plan) => plan.items.map((item) => item.customerOrderItemId)),
))

function localToday() {
  const today = new Date()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${today.getFullYear()}-${month}-${day}`
}

function itemDetail(itemId: number) {
  return activeOrder.value?.items.find((item) => item.id === itemId)
}

function selectedItems(): PlanItemInput[] {
  return form.items.filter((item) => item.selected).map((item) => ({
    customerOrderItemId: item.id,
    plannedFinishedQuantity: item.plannedFinishedQuantity,
  }))
}

function currentSignature() {
  return JSON.stringify(selectedItems())
}

function changeOrder() {
  form.items = activeOrder.value?.items.map((item) => ({
    id: item.id,
    selected: false,
    plannedFinishedQuantity: item.quantity,
  })) ?? []
  preview.value = undefined
  previewSignature.value = ''
}

async function loadData() {
  loading.value = true
  try {
    ;[plans.value, orders.value] = await Promise.all([
      queryV2ProductionPlans(),
      queryV2CustomerOrders(),
    ])
  } catch {
    ElMessage.error('生产计划资料加载失败')
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  editingPlanId.value = undefined
  form.customerOrderId = undefined
  form.startDate = localToday()
  form.completionDate = ''
  form.items = []
  preview.value = undefined
  previewSignature.value = ''
  dialogVisible.value = true
}

function openEditDialog(plan: ProductionPlan) {
  editingPlanId.value = plan.id
  form.customerOrderId = plan.customerOrderId
  form.startDate = plan.startDate
  form.completionDate = plan.completionDate
  const selectedMap = new Map(plan.items.map(
    (item) => [item.customerOrderItemId, item.plannedFinishedQuantity],
  ))
  form.items = activeOrder.value?.items.map((item) => ({
    id: item.id,
    selected: selectedMap.has(item.id),
    plannedFinishedQuantity: selectedMap.get(item.id) ?? item.quantity,
  })) ?? []
  preview.value = JSON.parse(JSON.stringify({
    customerOrderId: plan.customerOrderId,
    items: plan.items,
  }))
  previewSignature.value = currentSignature()
  dialogVisible.value = true
}

async function calculatePreview() {
  const items = selectedItems()
  if (!form.customerOrderId || !items.length) {
    ElMessage.warning('请选择客户订单明细')
    return
  }
  try {
    preview.value = editingPlanId.value
      ? await previewV2ProductionPlanUpdate(editingPlanId.value, items)
      : await previewV2ProductionPlan(form.customerOrderId, items)
    previewSignature.value = currentSignature()
  } catch {
    ElMessage.error(
      '理论数量计算失败，请检查BOM、半成品组成和路线是否已发布',
    )
  }
}

async function savePlan() {
  if (
    !form.customerOrderId
    || !form.startDate
    || !form.completionDate
    || !preview.value
    || previewSignature.value !== currentSignature()
  ) {
    ElMessage.warning('请填写日期，并在保存前重新计算理论数量')
    return
  }
  const materialAdjustments = preview.value.items.flatMap((item) => (
    item.materials.map((material) => ({
      customerOrderItemId: item.customerOrderItemId,
      materialId: material.materialId,
      plannedQuantity: material.plannedQuantity,
      adjustmentReason: material.adjustmentReason ?? undefined,
    }))
  ))
  const basePayload = {
    startDate: form.startDate,
    completionDate: form.completionDate,
    items: selectedItems(),
    materialAdjustments,
  }
  try {
    if (editingPlanId.value) {
      await updateV2ProductionPlan(editingPlanId.value, basePayload)
    } else {
      await createV2ProductionPlan({
        customerOrderId: form.customerOrderId,
        ...basePayload,
      })
    }
    dialogVisible.value = false
    await loadData()
    ElMessage.success('生产计划草稿已保存')
  } catch {
    ElMessage.error('生产计划保存失败，请检查调整原因和版本配置')
  }
}

async function executeAction(plan: ProductionPlan, action: 'release' | 'cancel') {
  try {
    await ElMessageBox.confirm(
      action === 'release'
        ? '下达后生产计划不能修改，确定继续？'
        : '确定取消生产计划？',
      '生产计划',
    )
    if (action === 'release') await releaseV2ProductionPlan(plan.id)
    else await cancelV2ProductionPlan(plan.id)
    await loadData()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('生产计划操作失败')
  }
}

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(loadData)
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div><span>生产计划部</span><h1>生产计划</h1></div>
      <div class="header-actions">
        <ElButton @click="router.push('/dashboard')">产品总览</ElButton>
        <ElSelect v-model="statusFilter" clearable placeholder="全部状态">
          <ElOption
            v-for="(label, value) in statusLabels"
            :key="value"
            :label="label"
            :value="value"
          />
        </ElSelect>
        <ElButton @click="loadData">查询</ElButton>
        <ElButton type="primary" @click="openCreateDialog">新增生产计划</ElButton>
        <ElButton @click="switchUser">切换用户</ElButton>
      </div>
    </header>

    <section v-loading="loading" class="content-card">
      <ElTable :data="displayedPlans" stripe>
        <ElTableColumn prop="planNo" label="计划号" width="180" />
        <ElTableColumn prop="customerName" label="客户" width="120" />
        <ElTableColumn prop="purchaseOrderNo" label="采购订单号" width="160" />
        <ElTableColumn label="计划产品" min-width="360">
          <template #default="{ row }">
            <div v-for="item in row.items" :key="item.customerOrderItemId">
              {{ item.factoryCode }} · {{ item.plannedFinishedQuantity }} pcs
              <span v-if="item.stockQuantity">（入库余量 {{ item.stockQuantity }}）</span>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="startDate" label="开始日期" width="120" />
        <ElTableColumn prop="completionDate" label="完成日期" width="120" />
        <ElTableColumn label="状态" width="100">
          <template #default="{ row }">{{ statusLabels[row.status] }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status === 'draft'">
              <ElButton text @click="openEditDialog(row)">编辑</ElButton>
              <ElButton text type="primary" @click="executeAction(row, 'release')">下达</ElButton>
              <ElButton text type="danger" @click="executeAction(row, 'cancel')">取消</ElButton>
            </template>
            <ElButton
              v-else-if="row.status === 'released'"
              text
              type="danger"
              @click="executeAction(row, 'cancel')"
            >
              取消
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>

    <ElDialog
      v-model="dialogVisible"
      :title="editingPlanId ? '编辑生产计划草稿' : '新增生产计划'"
      width="1120px"
    >
      <div class="plan-fields">
        <ElSelect
          v-model="form.customerOrderId"
          :disabled="Boolean(editingPlanId)"
          filterable
          placeholder="选择客户订单"
          @change="changeOrder"
        >
          <ElOption
            v-for="order in availableOrders"
            :key="order.id"
            :label="`${order.customerName} · ${order.purchaseOrderNo} · V${order.versionNo}`"
            :value="order.id"
          />
        </ElSelect>
        <ElDatePicker
          v-model="form.startDate"
          value-format="YYYY-MM-DD"
          placeholder="开始日期"
        />
        <ElDatePicker
          v-model="form.completionDate"
          value-format="YYYY-MM-DD"
          placeholder="完成日期"
        />
      </div>

      <ElTable :data="form.items" class="selection-table">
        <ElTableColumn label="选择" width="70">
          <template #default="{ row }">
            <ElCheckbox v-model="row.selected" :disabled="usedOrderItemIds.has(row.id)" />
          </template>
        </ElTableColumn>
        <ElTableColumn label="产品" min-width="280">
          <template #default="{ row }">
            {{ itemDetail(row.id)?.factoryCode }} · {{ itemDetail(row.id)?.productName }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="订单数量" width="110">
          <template #default="{ row }">{{ itemDetail(row.id)?.quantity }}</template>
        </ElTableColumn>
        <ElTableColumn label="计划成品数量" width="180">
          <template #default="{ row }">
            <ElInputNumber
              v-model="row.plannedFinishedQuantity"
              :min="itemDetail(row.id)?.quantity || 1"
              :disabled="!row.selected"
            />
          </template>
        </ElTableColumn>
        <ElTableColumn label="交货日期" width="130">
          <template #default="{ row }">{{ itemDetail(row.id)?.deliveryDate }}</template>
        </ElTableColumn>
      </ElTable>
      <div class="calculate-bar">
        <ElButton type="primary" plain @click="calculatePreview">计算理论数量</ElButton>
      </div>

      <template v-if="preview">
        <section
          v-for="item in preview.items"
          :key="item.customerOrderItemId"
          class="material-section"
        >
          <h3>{{ item.factoryCode }} · 计划成品 {{ item.plannedFinishedQuantity }} pcs</h3>
          <ElTable :data="item.materials" size="small" border>
            <ElTableColumn prop="materialCode" label="物料编号" width="150" />
            <ElTableColumn prop="materialName" label="物料名称" min-width="150" />
            <ElTableColumn prop="theoreticalQuantity" label="理论数量" width="100" />
            <ElTableColumn label="计划数量" width="160">
              <template #default="{ row }">
                <ElInputNumber
                  v-model="row.plannedQuantity"
                  :min="1"
                  :disabled="row.materialType === 'finished'"
                />
              </template>
            </ElTableColumn>
            <ElTableColumn label="调整原因" min-width="220">
              <template #default="{ row }">
                <ElInput
                  v-model="row.adjustmentReason"
                  :disabled="row.plannedQuantity === row.theoreticalQuantity"
                  placeholder="数量不同时必填"
                />
              </template>
            </ElTableColumn>
          </ElTable>
        </section>
      </template>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="savePlan">保存草稿</ElButton>
      </template>
    </ElDialog>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: 22px; background: var(--erp-bg); }
.page-header, .content-card {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  padding: 16px 20px;
}
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 6px 0 0; }
.header-actions, .plan-fields, .calculate-bar { display: flex; gap: 10px; }
.header-actions { flex-wrap: wrap; justify-content: flex-end; }
.header-actions :deep(.el-select) { width: 150px; }
.content-card { padding: 18px; }
.plan-fields { margin-bottom: 16px; }
.plan-fields :deep(.el-select) { flex: 1; }
.selection-table { margin-bottom: 12px; }
.calculate-bar { justify-content: flex-end; margin-bottom: 16px; }
.material-section { margin-top: 18px; }
.material-section h3 { margin: 0 0 10px; }
@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .plan-fields { display: grid; grid-template-columns: 1fr; }
}
</style>
