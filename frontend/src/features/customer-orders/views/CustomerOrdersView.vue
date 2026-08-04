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
import OrderProductProgress from '../components/OrderProductProgress.vue'

const props = withDefaults(defineProps<{
  embedded?: boolean
  readOnly?: boolean
  showProductProgress?: boolean
}>(), {
  embedded: false,
  readOnly: false,
  showProductProgress: false,
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
const statusLabels = {
  draft: '草稿', confirmed: '已确认', planned: '生产中', cancelled: '已取消', closed: '已完成',
}
const statusTagTypes = {
  draft: 'info',
  confirmed: 'primary',
  planned: 'warning',
  cancelled: 'danger',
  closed: 'success',
} as const
const filteredOrders = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  return value ? orders.value.filter((item) =>
    `${item.customer_order_no} ${item.customer_name}`.toLowerCase().includes(value),
  ) : orders.value
})

async function loadOrders() {
  loading.value = true
  try {
    const result = await queryCustomerOrders(
      page.value,
      pageSize,
      props.showProductProgress,
    )
    orders.value = result.items
    total.value = result.total
  }
  catch { ElMessage.error('客户订单加载失败') }
  finally { loading.value = false }
}

async function act(order: CustomerOrder, action: 'confirm' | 'cancel' | 'delete') {
  try {
    await ElMessageBox.confirm('确认执行该操作？', '客户订单', { type: 'warning' })
    if (action === 'confirm') {
      await confirmCustomerOrder(order.id, order.revision)
    }
    else if (action === 'cancel') await cancelCustomerOrder(order.id, order.revision)
    else await deleteCustomerOrder(order.id, order.revision)
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '订单操作失败')
    }
  }
}

async function openOrder(order: CustomerOrder) {
  if (props.readOnly) {
    await router.push({
      path: '/pmc',
      query: {
        tab: 'parts',
        orderId: String(order.id),
      },
    })
    return
  }
  if (order.status === 'draft' && !props.readOnly) {
    await router.push(`/business/orders/${order.id}`)
    return
  }
  activeOrderId.value = order.id
  detailVisible.value = true
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
      <ElTable v-loading="loading" :data="filteredOrders" border>
        <ElTableColumn prop="customer_name" label="客户名称" />
        <ElTableColumn prop="customer_order_no" label="订单编号"/>
        <ElTableColumn label="产品明细" min-width="260">
          <template #default="{ row }"><div v-for="item in row.items" :key="item.id">{{ item.factory_code }}-{{ item.product_name }}-{{ item.quantity }}个</div></template>
        </ElTableColumn>
        <ElTableColumn v-if="props.showProductProgress" label="产品进度" min-width="540">
          <template #default="{ row }">
            <OrderProductProgress
              v-for="progress in row.product_progress"
              :key="progress.customer_order_item_id"
              :progress="progress"
            />
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100">
          <template #default="{ row }">
            <ElTag :type="statusTagTypes[row.status as keyof typeof statusTagTypes]" effect="light">
              {{ statusLabels[row.status as keyof typeof statusLabels] }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" width="170" />
        <ElTableColumn label="操作" :width="props.readOnly ? 90 : 240" fixed="right">
          <template #default="{ row }">
            <ElButton link @click="openOrder(row)">{{ props.readOnly ? '查看' : row.status === 'draft' ? '编辑' : '查看' }}</ElButton>
            <template v-if="!props.readOnly">
              <ElButton v-if="row.status === 'draft'" v-permission="ORDER_PERMISSIONS.confirm" link type="primary" @click="act(row, 'confirm')">确认订单</ElButton>
              <ElButton v-if="['draft', 'confirmed', 'planned'].includes(row.status)" v-permission="ORDER_PERMISSIONS.cancel" link type="warning" @click="act(row, 'cancel')">取消</ElButton>
              <ElButton v-if="row.status === 'draft'" v-permission="ORDER_PERMISSIONS.edit" link type="danger" @click="act(row, 'delete')">删除</ElButton>
            </template>
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
