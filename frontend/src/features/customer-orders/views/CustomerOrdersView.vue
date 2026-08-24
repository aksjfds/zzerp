<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import { ORDER_PERMISSIONS } from '@/permission/constants'
import { useAuthStore } from '@/stores/auth'
import CustomerOrderEditorView from './CustomerOrderEditorView.vue'
import {
  cancelCustomerOrder,
  confirmCustomerOrder,
  deleteCustomerOrder,
  queryCustomerOrders,
} from '../api/customerOrders'
import type { CustomerOrder } from '../domain/types'
import {
  customerOrderStatusLabel,
  customerOrderStatusTagType,
} from '../domain/orderStatus'

const props = withDefaults(defineProps<{
  embedded?: boolean
}>(), {
  embedded: false,
})
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const keyword = ref('')
const orders = ref<CustomerOrder[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const detailVisible = ref(false)
const activeOrderId = ref<number>()
const filteredOrders = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  return value ? orders.value.filter((item) =>
    `${item.customer_order_no} ${item.customer_name}`.toLowerCase().includes(value),
  ) : orders.value
})

async function loadOrders() {
  loading.value = true
  try {
    const result = await queryCustomerOrders(page.value, pageSize)
    orders.value = result.items
    total.value = result.total
  }
  catch { ElMessage.error('客户订单加载失败') }
  finally { loading.value = false }
}

async function act(order: CustomerOrder, action: 'confirm' | 'cancel' | 'delete') {
  const prompts = {
    confirm: {
      title: '确认客户订单',
      message: '确认后，系统会创建一份待填写的生产计划。是否继续？',
      success: '客户订单已确认',
    },
    cancel: {
      title: '取消客户订单',
      message: '确定取消这个客户订单吗？',
      success: '客户订单已取消',
    },
    delete: {
      title: '删除订单草稿',
      message: '删除后无法恢复，确定删除这个订单草稿吗？',
      success: '订单草稿已删除',
    },
  } as const
  const prompt = prompts[action]
  try {
    await ElMessageBox.confirm(prompt.message, prompt.title, {
      type: action === 'confirm' ? 'info' : 'warning',
      confirmButtonText: action === 'delete' ? '确认删除' : '确认',
      cancelButtonText: '返回',
    })
    if (action === 'confirm') {
      await confirmCustomerOrder(order.id, order.revision)
    }
    else if (action === 'cancel') await cancelCustomerOrder(order.id, order.revision)
    else await deleteCustomerOrder(order.id, order.revision)
    ElMessage.success(prompt.success)
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '订单操作失败')
    }
  }
}

async function viewOrder(order: CustomerOrder) {
  activeOrderId.value = order.id
  detailVisible.value = true
}

async function editOrder(order: CustomerOrder) {
  await router.push(`/business/orders/${order.id}`)
}

function hasMoreActions(order: CustomerOrder) {
  return (
    ['draft', 'confirmed', 'planned'].includes(order.status)
    && authStore.hasPermission(ORDER_PERMISSIONS.cancel)
  ) || (
    order.status === 'draft'
    && authStore.hasPermission(ORDER_PERMISSIONS.edit)
  )
}

async function handleMoreAction(order: CustomerOrder, action: string | number | object) {
  if (action === 'cancel' || action === 'delete') await act(order, action)
}

async function logout() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(loadOrders)
defineExpose({ load: loadOrders })
</script>

<template>
  <main class="page-shell" :class="{ embedded: props.embedded }">
    <header v-if="!props.embedded" class="page-header">
      <div><span>业务部</span><h1>客户订单</h1></div>
      <div>
        <ElButton @click="logout">退出登录</ElButton>
        <ElButton v-permission="ORDER_PERMISSIONS.add" type="primary" @click="router.push('/business/orders/new')">创建客户订单</ElButton>
      </div>
    </header>
    <section class="content-card" :class="{ embedded: props.embedded }">
      <ElInput v-model="keyword" clearable placeholder="搜索当前页的订单编号或客户" class="search" />
      <ElTable v-table-column-widths="'sales.customer-orders'" v-loading="loading" :data="filteredOrders" border table-layout="auto">
        <ElTableColumn prop="customer_name" label="客户名称" min-width="150" />
        <ElTableColumn prop="customer_order_no" label="订单编号" min-width="160" />
        <ElTableColumn label="产品明细" min-width="260">
          <template #default="{ row }"><div v-for="item in row.items" :key="item.id">{{ item.factory_code }}-{{ item.product_name }}-{{ item.quantity }}个</div></template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100">
          <template #default="{ row }">
            <ElTag :type="customerOrderStatusTagType(row.status)" effect="light">
              {{ customerOrderStatusLabel(row.status) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" width="170" />
        <ElTableColumn label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <ElButton link @click="viewOrder(row)">查看</ElButton>
              <ElButton
                v-if="row.can_edit"
                v-permission="ORDER_PERMISSIONS.edit"
                link
                :type="row.status === 'cancelled' ? 'primary' : undefined"
                @click="editOrder(row)"
              >编辑</ElButton>
              <ElButton
                v-if="row.status === 'draft'"
                v-permission="ORDER_PERMISSIONS.confirm"
                link
                type="primary"
                @click="act(row, 'confirm')"
              >确认订单</ElButton>
              <ElDropdown
                v-if="hasMoreActions(row)"
                trigger="click"
                @command="handleMoreAction(row, $event)"
              >
                <ElButton link>更多</ElButton>
                <template #dropdown>
                  <ElDropdownMenu>
                    <ElDropdownItem
                      v-if="['draft', 'confirmed', 'planned'].includes(row.status)"
                      v-permission="ORDER_PERMISSIONS.cancel"
                      command="cancel"
                    >取消订单</ElDropdownItem>
                    <ElDropdownItem
                      v-if="row.status === 'draft'"
                      v-permission="ORDER_PERMISSIONS.edit"
                      command="delete"
                      divided
                    >删除草稿</ElDropdownItem>
                  </ElDropdownMenu>
                </template>
              </ElDropdown>
            </div>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElPagination
        v-model:current-page="page"
        class="pagination"
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="total"
        @current-change="loadOrders"
      />
    </section>
    <ElDialog v-model="detailVisible" title="客户订单详情" width="min(1100px, 92vw)" destroy-on-close>
      <CustomerOrderEditorView v-if="activeOrderId" :order-id="activeOrderId" embedded />
      <template #footer><ElButton @click="detailVisible = false">关闭</ElButton></template>
    </ElDialog>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--md-surface); }
.page-shell.embedded { min-height: auto; padding: 0; background: transparent; }
.page-header, .content-card { border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; padding: 20px 24px; background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 5px 0 0; font-size: 24px; font-weight: 600; letter-spacing: -.02em; }
.content-card { padding: 20px; }
.content-card.embedded { border: 0; box-shadow: none; padding: 0; }
.search { width: min(384px, 100%); margin-bottom: 16px; }
.row-actions { display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.row-actions :deep(.el-button) { margin-left: 0; }
.pagination { justify-content: flex-end; margin-top: 16px; }
@media (max-width: 760px) {
  .page-shell:not(.embedded) { padding: 16px; }
  .page-header { align-items: flex-start; flex-direction: column; gap: 16px; padding: 16px; }
  .page-header > div:last-child { display: grid; width: 100%; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .page-header :deep(.el-button) { width: 100%; margin: 0; }
  .content-card { padding: 16px; }
  .search { width: 100%; }
}
@media (max-width: 480px) {
  .page-shell:not(.embedded) { padding: 12px; }
  .content-card { padding: 12px; }
  .page-header > div:last-child { grid-template-columns: 1fr; }
}
</style>
