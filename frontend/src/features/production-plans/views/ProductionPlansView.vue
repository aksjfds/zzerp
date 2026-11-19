<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { PLAN_PERMISSIONS } from '@/permission/constants'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/shared/layout/PageHeader.vue'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryPlans, changePlanStatus, deletePlan } from '../api/plans'
import PlanEditor from '../components/PlanEditor.vue'
import DepartmentWorkOrdersPanel from '../components/DepartmentWorkOrdersPanel.vue'
import type { PlanAction, PlanStatus, ProductionPlan } from '../domain/types'

const auth = useAuthStore()
const plans = ref<ProductionPlan[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const dialog = ref(false)
const workOrderPlan = ref<ProductionPlan>()
const workOrderDialog = ref(false)
const selected = ref<ProductionPlan>()
const editorBusy = ref(false)
const commandBusy = ref(false)
const readonly = ref(false)
let sequence = 0
const labels: Record<PlanStatus, string> = { draft: '草稿', confirmed: '已确认', cancelled: '已取消', completed: '已完成' }
const actions: { action: PlanAction; label: string; statuses: PlanStatus[]; permission: string }[] = [
  { action: 'confirm', label: '确认', statuses: ['draft'], permission: PLAN_PERMISSIONS.confirm },
  { action: 'unconfirm', label: '撤回确认', statuses: ['confirmed'], permission: PLAN_PERMISSIONS.confirm },
  { action: 'complete', label: '完成', statuses: ['confirmed'], permission: PLAN_PERMISSIONS.confirm },
  { action: 'reopen', label: '恢复', statuses: ['completed'], permission: PLAN_PERMISSIONS.confirm },
  { action: 'cancel', label: '取消', statuses: ['draft', 'confirmed'], permission: PLAN_PERMISSIONS.cancel },
]

async function load() {
  const current = ++sequence
  loading.value = true
  error.value = ''
  plans.value = []
  try {
    const result = await queryPlans(page.value)
    if (current !== sequence) return
    if (!result.data.length && page.value > 1 && result.total <= (page.value - 1) * 50) {
      page.value = Math.max(1, Math.ceil(result.total / 50))
      await load()
      return
    }
    plans.value = result.data
    total.value = result.total
  } catch (cause) {
    if (current === sequence) error.value = getApiErrorDetail(cause)?.message || '生产计划加载失败'
  } finally {
    if (current === sequence) loading.value = false
  }
}

function open(plan?: ProductionPlan, viewOnly = false) {
  selected.value = plan
  readonly.value = viewOnly
  dialog.value = true
}

async function saved() {
  dialog.value = false
  await load()
}

async function act(plan: ProductionPlan, action: PlanAction | 'delete', label: string) {
  if (commandBusy.value) return
  commandBusy.value = true
  try {
    await ElMessageBox.confirm(`确定${label}订单号为“${plan.order_no}”的生产计划吗？`, `${label}生产计划`, { type: 'warning' })
    if (action === 'delete') await deletePlan(plan)
    else await changePlanStatus(plan, action)
    ElMessage.success(`生产计划已${label}`)
    await load()
  } catch (cause) {
    if (cause !== 'cancel' && cause !== 'close') ElMessage.error(getApiErrorDetail(cause)?.message || '操作失败')
  } finally {
    commandBusy.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => { sequence += 1 })
</script>

<template>
  <main class="plans-page">
    <PageHeader section-name="计划管理" page-title="生产计划">
      <template #actions>
        <ElButton v-permission="PLAN_PERMISSIONS.add" type="primary" @click="open()">＋ 新建计划</ElButton>
      </template>
    </PageHeader>
    <div class="overview-grid" aria-label="计划概览" :aria-busy="loading">
      <section class="overview-item"><span>计划总数</span><strong>{{ loading || error ? '—' : total }}</strong></section>
      <section class="overview-item"><span>本页待确认</span><strong>{{ loading || error ? '—' : plans.filter(item => item.status === 'draft').length }}</strong></section>
      <section class="overview-item"><span>本页已确认</span><strong>{{ loading || error ? '—' : plans.filter(item => item.status === 'confirmed').length }}</strong></section>
    </div>
    <section class="plans-card">
      <div class="collection-heading"><div><h2>订单计划</h2></div><ElButton :loading="loading" @click="load">刷新</ElButton></div>
      <LoadErrorAlert v-if="error" :message="error" :loading="loading" @retry="load" />
      <div v-else v-loading="loading" class="order-plans">
        <ElEmpty v-if="!loading && !plans.length" description="暂无生产计划" />
        <section v-for="plan in plans" :key="plan.id" class="order-plan" :aria-label="`订单 ${plan.order_no}`">
          <header class="order-heading">
            <div><span>{{ plan.customer_name }}</span><h3><ElButton link type="primary" @click="open(plan, true)">{{ plan.order_no }}</ElButton></h3></div>
            <ElTag :type="plan.status === 'completed' ? 'success' : plan.status === 'cancelled' ? 'info' : plan.status === 'confirmed' ? 'primary' : 'warning'">{{ labels[plan.status] }}</ElTag>
            <span>更新时间：{{ plan.updated_at }}</span>
          </header>
          <div class="row-actions">
            <ElButton link type="primary" @click="open(plan, true)">查看</ElButton>
            <ElButton v-if="plan.status !== 'draft' && plan.confirmed_at" link type="primary" @click="workOrderPlan = plan; workOrderDialog = true">部门安排</ElButton>
            <template v-if="plan.status === 'draft' || plan.status === 'cancelled'">
              <ElButton v-permission="PLAN_PERMISSIONS.edit" link type="primary" @click="open(plan)">编辑</ElButton>
              <ElButton v-permission="PLAN_PERMISSIONS.edit" link type="danger" :disabled="commandBusy" @click="act(plan, 'delete', '删除')">删除</ElButton>
            </template>
            <template v-for="item in actions" :key="item.action">
              <ElButton v-if="item.statuses.includes(plan.status) && auth.hasPermission(item.permission)" link type="primary" :disabled="commandBusy" @click="act(plan, item.action, item.label)">{{ item.label }}</ElButton>
            </template>
          </div>
          <ElTable v-table-column-widths="'planning.plan-products'" :data="plan.items" row-key="product_id" stripe table-layout="auto" empty-text="暂无产品">
            <ElTableColumn class-name="data-primary" label="产品" min-width="260"><template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template></ElTableColumn>
            <ElTableColumn prop="source_version_value" label="外观版本" min-width="140" show-overflow-tooltip />
            <ElTableColumn prop="order_quantity" label="订单数量" min-width="120" align="right" />
            <ElTableColumn class-name="data-metric" prop="production_quantity" label="生产数量" min-width="120" align="right" />
            <ElTableColumn label="下单日期" min-width="140"><template #default>{{ plan.order_date }}</template></ElTableColumn>
            <ElTableColumn label="交货日期" min-width="140"><template #default>{{ plan.delivery_date }}</template></ElTableColumn>
          </ElTable>
        </section>
      </div>
      <ElPagination v-if="!error" v-model:current-page="page" class="pagination" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </section>
    <ElDialog v-model="workOrderDialog" :title="`部门安排 · ${workOrderPlan?.order_no || ''}`" width="min(1120px, 96vw)" destroy-on-close>
      <DepartmentWorkOrdersPanel v-if="workOrderDialog && workOrderPlan" :plan-id="workOrderPlan.id" />
    </ElDialog>
    <ElDialog v-model="dialog" :title="readonly ? '查看生产计划' : selected ? '编辑生产计划' : '创建生产计划'" width="min(640px, 94vw)" destroy-on-close :close-on-click-modal="!editorBusy" :close-on-press-escape="!editorBusy" :show-close="!editorBusy">
      <PlanEditor v-if="dialog" :plan="selected" :readonly="readonly" @saved="saved" @busy="editorBusy = $event" />
    </ElDialog>
  </main>
</template>

<style scoped>
.plans-card { min-width: 0; }
.plans-page { padding: 32px; background: var(--erp-bg); }
.plans-card { padding: 24px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
.collection-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.collection-heading h2 { margin: 0; font-size: 20px; }
.order-plans { min-height: 80px; }
.order-plan { margin-top: 20px; padding: 16px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); }
.order-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; margin-bottom: 12px; }
.order-heading > div { margin-right: auto; }
.order-heading h3 { margin: 4px 0 0; }
.order-heading h3 :deep(.el-button) { height: auto; font-size: 22px; font-weight: 700; white-space: normal; overflow-wrap: anywhere; text-align: left; }
.order-heading > span:not(.el-tag), .order-heading > div > span { color: var(--erp-text-secondary); }
.row-actions { margin-bottom: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
.row-actions :deep(.el-button) { margin-left: 0; }
.pagination { margin-top: 16px; justify-content: flex-end; }
@media (max-width: 760px) { .plans-page { padding: 24px 16px; } .plans-card { padding: 16px; } }
</style>
