<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
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
const router = useRouter()
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

async function logout() {
  await auth.logout()
  await router.replace('/login')
}

onMounted(load)
onBeforeUnmount(() => { sequence += 1 })
</script>

<template>
  <main class="plans-page">
    <PageHeader section-name="计划管理" page-title="生产计划">
      <template #actions>
        <ElButton @click="router.push('/department-work-orders')">生产进度查看</ElButton>
        <ElButton @click="logout">退出登录</ElButton>
        <ElButton v-permission="PLAN_PERMISSIONS.add" type="primary" @click="open()">创建生产计划</ElButton>
      </template>
    </PageHeader>
    <section class="plans-card">
      <div class="plans-heading"><h2>生产计划</h2><ElButton :loading="loading" @click="load">刷新</ElButton></div>
      <LoadErrorAlert v-if="error" :message="error" :loading="loading" @retry="load" />
      <ElTable v-else v-table-column-widths="'planning.plans'" v-loading="loading" :data="plans" border stripe table-layout="auto" empty-text="暂无生产计划">
        <ElTableColumn prop="order_no" label="订单号" min-width="160" />
        <ElTableColumn prop="customer_name" label="客户" min-width="140" />
        <ElTableColumn label="产品" min-width="220"><template #default="{ row }">{{ row.factory_code }} · {{ row.product_name }}</template></ElTableColumn>
        <ElTableColumn prop="order_quantity" label="订单数量" width="110" align="right" />
        <ElTableColumn prop="production_quantity" label="生产数量" width="110" align="right" />
        <ElTableColumn label="状态" width="100"><template #default="{ row }">{{ labels[row.status as PlanStatus] }}</template></ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" min-width="170" />
        <ElTableColumn label="操作" min-width="320">
          <template #default="{ row }">
            <div class="row-actions">
              <ElButton link type="primary" @click="open(row, true)">查看</ElButton>
              <ElButton link type="primary" @click="workOrderPlan = row; workOrderDialog = true">部门安排</ElButton>
              <template v-if="row.status === 'draft' || row.status === 'cancelled'">
                <ElButton v-permission="PLAN_PERMISSIONS.edit" link type="primary" @click="open(row)">编辑</ElButton>
                <ElButton v-permission="PLAN_PERMISSIONS.edit" link type="danger" :disabled="commandBusy" @click="act(row, 'delete', '删除')">删除</ElButton>
              </template>
              <template v-for="item in actions" :key="item.action">
                <ElButton v-if="item.statuses.includes(row.status) && auth.hasPermission(item.permission)" link type="primary" :disabled="commandBusy" @click="act(row, item.action, item.label)">{{ item.label }}</ElButton>
              </template>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElPagination v-if="!error" v-model:current-page="page" class="pagination" :page-size="50" :total="total" layout="prev, pager, next, total" @current-change="load" />
    </section>
    <ElDialog v-model="workOrderDialog" :title="`部门安排 · ${workOrderPlan?.order_no || ''}`" width="min(1380px, 96vw)" destroy-on-close>
      <DepartmentWorkOrdersPanel v-if="workOrderDialog && workOrderPlan" :plan-id="workOrderPlan.id" />
    </ElDialog>
    <ElDialog v-model="dialog" :title="readonly ? '查看生产计划' : selected ? '编辑生产计划' : '创建生产计划'" width="min(760px, 94vw)" destroy-on-close :close-on-click-modal="!editorBusy" :close-on-press-escape="!editorBusy" :show-close="!editorBusy">
      <PlanEditor v-if="dialog" :plan="selected" :readonly="readonly" @saved="saved" @busy="editorBusy = $event" />
    </ElDialog>
  </main>
</template>

<style scoped>
.plans-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--erp-bg); }
.plans-card { padding: 20px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); }
.plans-heading { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 16px; }
.plans-heading h2 { margin: 0; font-size: 20px; }
.row-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.row-actions :deep(.el-button) { margin-left: 0; }
.pagination { margin-top: 16px; justify-content: flex-end; }
@media (max-width: 640px) { .plans-card { padding: 12px; } }
</style>
