<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import { ORDER_PERMISSIONS } from '@/permission/constants'
import { useAuthStore } from '@/stores/auth'
import {
  cancelCustomerOrder,
  confirmCustomerOrder,
  deleteCustomerOrder,
  queryCustomerOrders,
} from '../api/customerOrders'
import type { CustomerOrder } from '../domain/types'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const keyword = ref('')
const orders = ref<CustomerOrder[]>([])
const statusLabels = {
  draft: '草稿', confirmed: '已确认', planned: '已排产', cancelled: '已取消', closed: '已完成',
}
const filteredOrders = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  return value ? orders.value.filter((item) =>
    `${item.customer_order_no} ${item.customer_name}`.toLowerCase().includes(value),
  ) : orders.value
})

async function loadOrders() {
  loading.value = true
  try { orders.value = await queryCustomerOrders() }
  catch { ElMessage.error('客户订单加载失败') }
  finally { loading.value = false }
}

async function act(order: CustomerOrder, action: 'confirm' | 'cancel' | 'delete') {
  try {
    await ElMessageBox.confirm('确认执行该操作？', '客户订单', { type: 'warning' })
    if (action === 'confirm') await confirmCustomerOrder(order.id)
    else if (action === 'cancel') await cancelCustomerOrder(order.id)
    else await deleteCustomerOrder(order.id)
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '订单操作失败')
    }
  }
}

async function logout() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(loadOrders)
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div><span>业务部</span><h1>客户订单</h1></div>
      <div>
        <ElButton @click="logout">退出登录</ElButton>
        <ElButton v-permission="ORDER_PERMISSIONS.add" type="primary" @click="router.push('/business/orders/new')">创建客户订单</ElButton>
      </div>
    </header>
    <section class="content-card">
      <ElInput v-model="keyword" clearable placeholder="搜索订单编号或客户" class="search" />
      <ElTable v-loading="loading" :data="filteredOrders" border>
        <ElTableColumn prop="customer_order_no" label="订单编号" min-width="160" />
        <ElTableColumn prop="customer_name" label="客户名称" min-width="140" />
        <ElTableColumn label="产品明细" min-width="260">
          <template #default="{ row }"><div v-for="item in row.items" :key="item.id">{{ item.factory_code }} · V{{ item.product_version }} · {{ item.quantity }}</div></template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100"><template #default="{ row }">{{ statusLabels[row.status as keyof typeof statusLabels] }}</template></ElTableColumn>
        <ElTableColumn prop="updated_at" label="更新时间" width="170" />
        <ElTableColumn label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <ElButton link @click="router.push(`/business/orders/${row.id}`)">{{ row.status === 'draft' ? '编辑' : '查看' }}</ElButton>
            <ElButton v-if="row.status === 'draft'" v-permission="ORDER_PERMISSIONS.confirm" link type="primary" @click="act(row, 'confirm')">确认</ElButton>
            <ElButton v-if="row.status === 'draft'" v-permission="ORDER_PERMISSIONS.cancel" link type="warning" @click="act(row, 'cancel')">取消</ElButton>
            <ElButton v-if="row.status === 'draft'" v-permission="ORDER_PERMISSIONS.edit" link type="danger" @click="act(row, 'delete')">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: 24px; background: var(--erp-bg); }
.page-header, .content-card { border: 1px solid var(--erp-border); border-radius: 10px; background: white; box-shadow: var(--erp-shadow-sm); }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; padding: 20px 24px; }
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 5px 0 0; }
.content-card { padding: 20px; }
.search { width: 360px; margin-bottom: 16px; }
</style>
