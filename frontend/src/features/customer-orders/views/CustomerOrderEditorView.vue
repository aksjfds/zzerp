<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import ProductionFlowViewer from '../components/ProductionFlowViewer.vue'
import { queryProduct, queryProducts } from '@/features/process-designer/api/engineeringProducts'
import type { EngineeringProduct, ProductSummary } from '@/features/process-designer/domain/types'
import { createCustomerOrder, queryCustomerOrder, queryCustomerOrderProduction, updateCustomerOrder } from '../api/customerOrders'
import type { CustomerOrderItem, CustomerOrderPayload, CustomerOrderProduction } from '../domain/types'

const route = useRoute()
const router = useRouter()
const props = withDefaults(defineProps<{ orderId?: number; embedded?: boolean }>(), {
  orderId: undefined,
  embedded: false,
})
const products = ref<ProductSummary[]>([])
const productLoading = ref(false)
let productSearchSequence = 0
const status = ref('draft')
const revision = ref<number | null>(null)
const production = ref<CustomerOrderProduction>()
const form = reactive({
  customer_order_no: '', customer_name: '', remark: '', items: [] as CustomerOrderItem[],
})
const effectiveOrderId = computed(() => props.orderId ?? (Number(route.params.orderId) || null))
const readOnly = computed(() => props.embedded || status.value !== 'draft')

function addItem() {
  form.items.push({ product_id: 0, quantity: 1, delivery_date: '', remark: '' })
}

function product(productId: number) {
  return products.value.find((item) => item.id === productId)
}

function asSummary(item: EngineeringProduct): ProductSummary {
  return {
    id: item.id,
    version: item.current_version,
    revision: item.revision,
    customer_name: item.customer_name,
    product_name: item.product_name,
    factory_code: item.factory_code,
    customer_code: item.customer_code,
    bom_count: item.bom_items.length,
    created_at: item.created_at,
    updated_at: item.updated_at,
  }
}

async function searchProducts(keyword = '') {
  const sequence = ++productSearchSequence
  productLoading.value = true
  try {
    const result = await queryProducts(1, 50, keyword)
    if (sequence !== productSearchSequence) return
    const selected = products.value.filter(item => (
      form.items.some(orderItem => orderItem.product_id === item.id)
    ))
    products.value = [
      ...selected,
      ...result.items.filter(item => !selected.some(selectedItem => selectedItem.id === item.id)),
    ]
  } finally {
    if (sequence === productSearchSequence) productLoading.value = false
  }
}

async function save() {
  if (!form.customer_order_no.trim() || !form.customer_name.trim() || !form.items.length
    || form.items.some((item) => !item.product_id || item.quantity < 1 || !item.delivery_date)) {
    return ElMessage.warning('请完整填写订单和产品明细')
  }
  try {
    const payload: CustomerOrderPayload = {
      customer_order_no: form.customer_order_no,
      customer_name: form.customer_name,
      remark: form.remark,
      items: form.items.map(({ product_id, quantity, delivery_date, remark }) => ({
        product_id, quantity, delivery_date, remark,
      })),
      expected_revision: revision.value ?? undefined,
    }
    if (effectiveOrderId.value) await updateCustomerOrder(effectiveOrderId.value, payload)
    else await createCustomerOrder(payload)
    ElMessage.success('客户订单已保存')
    router.push('/business/orders')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '客户订单保存失败')
  }
}

onMounted(async () => {
  await searchProducts()
  if (effectiveOrderId.value) {
    const order = await queryCustomerOrder(effectiveOrderId.value)
    production.value = await queryCustomerOrderProduction(effectiveOrderId.value)
    status.value = order.status
    revision.value = order.revision
    Object.assign(form, {
      customer_order_no: order.customer_order_no,
      customer_name: order.customer_name,
      remark: order.remark,
      items: order.items.map((item): CustomerOrderItem => ({ ...item })),
    })
    const missingIds = [...new Set(
      order.items.map(item => item.product_id).filter(id => !product(id)),
    )]
    if (missingIds.length) {
      const missing = await Promise.all(missingIds.map(id => queryProduct(id)))
      products.value.push(...missing.map(asSummary))
    }
  } else addItem()
})
</script>

<template>
  <main class="editor-page" :class="{ embedded: props.embedded }">
    <header v-if="!props.embedded"><div><span>业务部</span><h1>{{ effectiveOrderId ? '客户订单详情' : '创建客户订单' }}</h1></div><div><ElButton @click="router.push('/business/orders')">返回</ElButton><ElButton v-if="!readOnly" type="primary" @click="save">保存草稿</ElButton></div></header>
    <section v-if="!effectiveOrderId" class="card">
      <ElForm :model="form" :disabled="readOnly" label-position="top">
        <div class="grid"><ElFormItem label="客户订单编号"><ElInput v-model="form.customer_order_no" /></ElFormItem><ElFormItem label="客户名称"><ElInput v-model="form.customer_name" /></ElFormItem></div>
        <ElFormItem label="备注"><ElInput v-model="form.remark" type="textarea" /></ElFormItem>
      </ElForm>
    </section>
    <section class="card" :class="{ readonly: readOnly }">
      <div class="heading"><h2>产品明细</h2><ElButton v-if="!readOnly" @click="addItem">新增产品</ElButton></div>
      <ElTable :data="form.items" border>
        <ElTableColumn label="产品" min-width="220"><template #default="{ row }"><ElSelect v-model="row.product_id" :disabled="readOnly" filterable remote :remote-method="searchProducts" :loading="productLoading"><ElOption v-for="item in products" :key="item.id" :value="item.id" :label="`${item.factory_code} · ${item.product_name}`" /></ElSelect></template></ElTableColumn>
        <ElTableColumn label="版本" width="80"><template #default="{ row }">V{{ row.product_version ?? product(row.product_id)?.version ?? '-' }}</template></ElTableColumn>
        <ElTableColumn label="数量" width="140"><template #default="{ row }"><ElInputNumber v-model="row.quantity" :disabled="readOnly" :min="1" /></template></ElTableColumn>
        <ElTableColumn label="交期" width="170"><template #default="{ row }"><ElDatePicker v-model="row.delivery_date" :disabled="readOnly" value-format="YYYY-MM-DD" /></template></ElTableColumn>
        <ElTableColumn label="备注" min-width="180"><template #default="{ row }"><ElInput v-model="row.remark" :disabled="readOnly" /></template></ElTableColumn>
        <ElTableColumn v-if="!readOnly" label="操作" width="80"><template #default="{ $index }"><ElButton link type="danger" @click="form.items.splice($index, 1)">删除</ElButton></template></ElTableColumn>
      </ElTable>
    </section>
    <section v-if="effectiveOrderId && production" class="card">
      <div class="heading"><h2>生产情况</h2></div>
      <div class="product-status-list">
        <section
          v-for="productStatus in production.products"
          :key="productStatus.customer_order_item_id"
          class="product-status-section"
        >
          <h3>{{ productStatus.factory_code }} · {{ productStatus.product_name }} · 订单数量 {{ productStatus.order_quantity }}</h3>
          <ProductionFlowViewer :flow="productStatus.process_flow" :stats="productStatus.node_stats" />
        </section>
      </div>
    </section>
  </main>
</template>

<style scoped>
.editor-page { min-height: 100vh; padding: 24px; background: var(--erp-bg); }
.editor-page.embedded { min-height: 0; padding: 0; background: transparent; }
.editor-page.embedded .card { box-shadow: none; }
header, .card { border: 1px solid var(--erp-border); border-radius: 10px; background: white; box-shadow: var(--erp-shadow-sm); }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; padding: 18px 22px; }
header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
header h1 { margin: 5px 0 0; }
.card { margin-bottom: 18px; padding: 20px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.heading { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.heading h2 { margin: 0; font-size: 18px; }
.product-status-section { margin-top: 14px; padding: 14px; border: 1px solid var(--erp-border); border-radius: 8px; }
.product-status-section h3 { margin: 0 0 12px; }
</style>
