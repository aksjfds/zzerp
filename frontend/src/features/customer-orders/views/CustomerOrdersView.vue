<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
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
const loadError = ref('')
let loadRevision = 0
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
  const revision = ++loadRevision
  loading.value = true
  loadError.value = ''
  orders.value = []
  try {
    const result = await queryCustomerOrders(page.value, pageSize)
    if (revision !== loadRevision) return
    orders.value = result.items
    total.value = result.total
  }
  catch (error) {
    if (revision === loadRevision) loadError.value = getApiErrorDetail(error)?.message || '客户订单加载失败'
  }
  finally { if (revision === loadRevision) loading.value = false }
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
      message: '确定取消这个客户订单吗？仅占用的成品库存会自动释放；已经实际出库、加工或送检时不能取消。',
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
    <DepartmentPageHeader v-if="!props.embedded" department-name="业务部" page-title="客户订单">
      <template #actions>
        <ElButton @click="logout">退出登录</ElButton>
        <ElButton v-permission="ORDER_PERMISSIONS.add" type="primary" @click="router.push('/business/orders/new')">创建客户订单</ElButton>
      </template>
    </DepartmentPageHeader>
    <section class="content-card" :class="{ embedded: props.embedded }">
      <ElInput v-model="keyword" clearable placeholder="搜索当前页的订单编号或客户" class="search" />
      <LoadErrorAlert v-if="loadError" :message="loadError" :loading="loading" @retry="loadOrders" />
      <ElTable v-else v-table-column-widths="'sales.customer-orders'" v-loading="loading" :data="filteredOrders" border table-layout="auto" empty-text="暂无符合条件的客户订单">
        <ElTableColumn prop="customer_name" label="客户名称" min-width="150" />
        <ElTableColumn prop="customer_order_no" label="订单编号" min-width="160" />
        <ElTableColumn label="产品明细" min-width="260">
          <template #default="{ row }"><div v-for="item in row.items" :key="item.id" class="product-summary"><strong>{{ item.factory_code }} · {{ item.product_name }}</strong><span>版本 {{ item.product_version ?? '—' }} · {{ item.quantity }} 个</span></div></template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100">
          <template #default="{ row }">
            <ElTag :type="customerOrderStatusTagType(row.status)" effect="light">
              {{ customerOrderStatusLabel(row.status) }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" width="170" />
        <ElTableColumn label="操作" min-width="250">
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
                      v-if="['draft', 'confirmed', 'planned'].includes(row.status) && authStore.hasPermission(ORDER_PERMISSIONS.cancel)"
                      command="cancel"
                    >取消订单</ElDropdownItem>
                    <ElDropdownItem
                      v-if="row.status === 'draft' && authStore.hasPermission(ORDER_PERMISSIONS.edit)"
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
        v-if="!loadError"
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
.content-card { border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); }
.content-card { padding: 20px; }
.content-card.embedded { border: 0; box-shadow: none; padding: 0; }
.search { width: min(384px, 100%); margin-bottom: 16px; }
.row-actions { display: flex; align-items: center; gap: 4px; white-space: nowrap; }
.row-actions :deep(.el-button) { margin-left: 0; }
.pagination { justify-content: flex-end; margin-top: 16px; }
.product-summary { display: grid; gap: 2px; }
.product-summary + .product-summary { margin-top: 8px; }
.product-summary span { color: var(--erp-text-secondary); font-size: 12px; font-variant-numeric: tabular-nums; }
@media (max-width: 760px) {
  .page-shell:not(.embedded) { padding: 16px; }
  .content-card { padding: 16px; }
  .search { width: 100%; }
}
@media (max-width: 480px) {
  .page-shell:not(.embedded) { padding: 12px; }
  .content-card { padding: 12px; }
}
</style>
