<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import { queryOrderProduct, queryOrderProducts, type OrderProduct } from '../api/orderProducts'
import { createCustomerOrder, queryCustomerOrder, updateCustomerOrder } from '../api/customerOrders'
import type { CustomerOrderItem, CustomerOrderPayload } from '../domain/types'
import { queryCustomers, type Customer } from '@/features/customers'
import { useAuthStore } from '@/stores/auth'
import { ORDER_PERMISSIONS } from '@/permission/constants'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const props = withDefaults(defineProps<{ orderId?: number; embedded?: boolean }>(), {
  orderId: undefined,
  embedded: false,
})
const products = ref<OrderProduct[]>([])
const customers = ref<Customer[]>([])
const customerLoading = ref(false)
const productLoading = ref(false)
const saving = ref(false)
let productSearchSequence = 0
const status = ref('draft')
const orderEditable = ref(true)
const revision = ref<number | null>(null)
const form = reactive({
  customer_order_no: '', customer_id: null as number | null, remark: '', items: [] as CustomerOrderItem[],
})
const effectiveOrderId = computed(() => props.orderId ?? (Number(route.params.orderId) || null))
const canEdit = computed(() => effectiveOrderId.value
  ? authStore.hasPermission(ORDER_PERMISSIONS.edit)
  : authStore.hasPermission(ORDER_PERMISSIONS.add))
const readOnly = computed(() => props.embedded || !orderEditable.value || !canEdit.value)

function addItem() {
  if (!form.customer_id) {
    ElMessage.warning('请先选择客户')
    return
  }
  form.items.push({ product_id: 0, quantity: 1, delivery_date: '', remark: '' })
}

function product(productId: number) {
  return products.value.find((item) => item.id === productId)
}

function productLabel(productId: number) {
  const item = product(productId)
  return item ? `${item.factory_code} · ${item.product_name}` : `产品 #${productId}`
}

async function searchProducts(keyword = '') {
  if (!form.customer_id) {
    products.value = []
    return
  }
  const sequence = ++productSearchSequence
  productLoading.value = true
  try {
    const result = await queryOrderProducts(form.customer_id, keyword)
    if (sequence !== productSearchSequence) return
    const selected = products.value.filter(item => (
      form.items.some(orderItem => orderItem.product_id === item.id)
    ))
    products.value = [
      ...selected,
      ...result.filter(item => !selected.some(selectedItem => selectedItem.id === item.id)),
    ]
  } finally {
    if (sequence === productSearchSequence) productLoading.value = false
  }
}

async function changeCustomer() {
  form.items = []
  products.value = []
  if (!form.customer_id) return
  await searchProducts()
  addItem()
}

async function save() {
  if (!form.customer_order_no.trim() || !form.customer_id || !form.items.length
    || form.items.some((item) => !item.product_id || item.quantity < 1 || !item.delivery_date)) {
    return ElMessage.warning('请完整填写订单和产品明细')
  }
  const unavailableProduct = form.items
    .map(item => product(item.product_id))
    .find(item => item && !item.order_ready)
  if (unavailableProduct) {
    return ElMessage.warning(`${unavailableProduct.factory_code} 不可用`)
  }
  saving.value = true
  try {
    const payload: CustomerOrderPayload = {
      customer_order_no: form.customer_order_no,
      customer_id: form.customer_id,
      remark: form.remark,
      items: form.items.map(({ id, product_id, quantity, delivery_date, remark }) => ({
        id, product_id, quantity, delivery_date, remark,
      })),
      expected_revision: revision.value ?? undefined,
    }
    if (effectiveOrderId.value) {
      await updateCustomerOrder(effectiveOrderId.value, payload)
    } else {
      await createCustomerOrder(payload)
      ElMessage.success('客户订单已创建，请确认订单')
      await router.push('/business/orders')
      return
    }
    ElMessage.success('客户订单已保存')
    router.push('/business/orders')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '客户订单保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  customerLoading.value = true
  try {
    customers.value = await queryCustomers()
  } finally {
    customerLoading.value = false
  }
  if (effectiveOrderId.value) {
    const order = await queryCustomerOrder(effectiveOrderId.value)
    status.value = order.status
    orderEditable.value = order.can_edit
    revision.value = order.revision
    Object.assign(form, {
      customer_order_no: order.customer_order_no,
      customer_id: order.customer_id,
      remark: order.remark,
      items: order.items.map((item): CustomerOrderItem => ({ ...item })),
    })
    await searchProducts()
    const missingIds = [...new Set(
      order.items.map(item => item.product_id).filter(id => !product(id)),
    )]
    if (missingIds.length) {
      const missing = await Promise.all(missingIds.map(id => queryOrderProduct(id)))
      products.value.push(...missing)
    }
  }
})
</script>

<template>
  <main class="editor-page" :class="{ embedded: props.embedded }">
    <header v-if="!props.embedded"><div><span>业务部</span><h1>{{ effectiveOrderId ? readOnly ? '客户订单详情' : '编辑客户订单' : '创建客户订单' }}</h1></div><div class="header-actions"><ElButton :disabled="saving" @click="router.push('/business/orders')">返回列表</ElButton><ElButton v-if="!readOnly" type="primary" :loading="saving" @click="save">保存草稿</ElButton></div></header>
    <section v-if="!props.embedded" class="card">
      <ElForm :model="form" :disabled="readOnly" label-position="top">
        <div class="grid">
          <ElFormItem label="客户订单编号"><ElInput v-model="form.customer_order_no" /></ElFormItem>
          <ElFormItem label="客户名称" required>
            <ElSelect
              v-model="form.customer_id"
              placement="top-start"
              :fallback-placements="['top-start', 'top-end']"
              filterable
              :loading="customerLoading"
              placeholder="请先选择客户"
              style="width: 100%"
              @change="changeCustomer"
            >
              <ElOption v-for="customer in customers" :key="customer.id" :label="customer.customer_name" :value="customer.id" />
            </ElSelect>
          </ElFormItem>
        </div>
        <ElFormItem label="备注"><ElInput v-model="form.remark" type="textarea" /></ElFormItem>
      </ElForm>
    </section>
    <section class="card" :class="{ readonly: readOnly }">
      <div class="heading"><h2>产品明细</h2><ElButton v-if="!readOnly" :disabled="!form.customer_id" @click="addItem">新增产品</ElButton></div>
      <ElTable v-table-column-widths="'sales.order-editor-items'" :data="form.items" border table-layout="auto">
        <ElTableColumn label="产品" min-width="220">
          <template #default="{ row }">
            <span v-if="readOnly" class="readonly-value">{{ productLabel(row.product_id) }}</span>
            <ElSelect v-else v-model="row.product_id" placement="top-start" :fallback-placements="['top-start', 'top-end']" :disabled="!form.customer_id" filterable remote :remote-method="searchProducts" :loading="productLoading" placeholder="选择该客户的产品">
              <ElOption
                v-for="item in products"
                :key="item.id"
                :value="item.id"
                :label="`${item.factory_code} · ${item.product_name}${item.order_ready ? '' : '（不可用）'}`"
                :disabled="!item.order_ready || form.items.some(other => other !== row && other.product_id === item.id)"
              />
            </ElSelect>
          </template>
        </ElTableColumn>
        <ElTableColumn label="版本" width="80"><template #default="{ row }">V{{ row.product_version ?? product(row.product_id)?.version ?? '-' }}</template></ElTableColumn>
        <ElTableColumn label="数量" width="140"><template #default="{ row }"><span v-if="readOnly" class="readonly-value readonly-number">{{ row.quantity }}</span><ElInputNumber v-else v-model="row.quantity" :min="1" /></template></ElTableColumn>
        <ElTableColumn label="交期" width="170"><template #default="{ row }"><span v-if="readOnly" class="readonly-value">{{ row.delivery_date || '-' }}</span><ElDatePicker v-else v-model="row.delivery_date" placement="top-start" :fallback-placements="['top-start', 'top-end']" value-format="YYYY-MM-DD" /></template></ElTableColumn>
        <ElTableColumn label="备注" min-width="180"><template #default="{ row }"><span v-if="readOnly" class="readonly-value">{{ row.remark || '-' }}</span><ElInput v-else v-model="row.remark" /></template></ElTableColumn>
        <ElTableColumn v-if="!readOnly" label="操作" width="80"><template #default="{ $index }"><ElButton link type="danger" @click="form.items.splice($index, 1)">删除</ElButton></template></ElTableColumn>
      </ElTable>
    </section>
  </main>
</template>

<style scoped>
.editor-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--md-surface); }
.editor-page.embedded { min-height: 0; padding: 0; background: transparent; }
.editor-page.embedded .card { box-shadow: none; }
header, .card { border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; padding: 18px 22px; background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
header h1 { margin: 5px 0 0; font-size: 24px; font-weight: 600; letter-spacing: -.02em; }
.card { margin-bottom: 18px; padding: 20px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.heading h2 { margin: 0; font-size: 18px; }
.readonly-value { color: var(--md-on-surface); line-height: 1.5; overflow-wrap: anywhere; }
.readonly-number { font-variant-numeric: tabular-nums; }
@media (max-width: 760px) {
  .editor-page:not(.embedded) { padding: 16px; }
  header { align-items: flex-start; flex-direction: column; gap: 16px; padding: 16px; }
  header > div:last-child { display: grid; width: 100%; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  header :deep(.el-button) { width: 100%; margin: 0; }
  .card { padding: 16px; }
  .grid { grid-template-columns: 1fr; gap: 0; }
  .heading { align-items: flex-start; flex-direction: column; gap: 10px; }
  .heading :deep(.el-button) { width: 100%; }
}
@media (max-width: 480px) {
  .editor-page:not(.embedded) { padding: 12px; }
  .card { padding: 12px; }
  header > div:last-child { grid-template-columns: 1fr; }
}
</style>
