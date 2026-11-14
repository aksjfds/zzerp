<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryCustomers, type Customer } from '@/features/customers'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryPlanProducts, savePlan, type PlanProduct } from '../api/plans'
import type { ProductionPlan, ProductionPlanInput, ProductionPlanItemInput } from '../domain/types'

const props = defineProps<{ plan?: ProductionPlan; readonly?: boolean }>()
const emit = defineEmits<{ saved: []; busy: [value: boolean] }>()
const customers = ref<Customer[]>([])
const products = ref<PlanProduct[]>([])
const customerLoading = ref(false)
const productLoading = ref(false)
const saving = ref(false)
const customerError = ref('')
const productError = ref('')
let active = true
let searchSequence = 0
const form = reactive({
  customer_id: props.plan?.customer_id as number | undefined,
  order_no: props.plan?.order_no || '',
  items: props.plan?.items.map(item => ({ product_id: item.product_id,
    order_quantity: item.order_quantity, production_quantity: item.production_quantity })) ?? [] as ProductionPlanItemInput[],
})
const selectedProducts = ref<PlanProduct[]>(props.plan?.items.map(item => ({
  id: item.product_id, customer_id: props.plan!.customer_id,
  product_name: item.product_name, factory_code: item.factory_code,
})) ?? [])
const selectedIds = computed(() => form.items.map(item => item.product_id))
const options = computed(() => {
  const byId = new Map([...selectedProducts.value, ...products.value].map(item => [item.id, item]))
  return [...byId.values()]
})
const disabled = computed(() => props.readonly || saving.value)

async function loadCustomers() {
  customerLoading.value = true
  customerError.value = ''
  try {
    const result = await queryCustomers()
    if (active) customers.value = result
  } catch (error) {
    if (active) customerError.value = getApiErrorDetail(error)?.message || '客户列表加载失败'
  } finally {
    if (active) customerLoading.value = false
  }
}

async function searchProducts(keyword = '') {
  const sequence = ++searchSequence
  products.value = []
  productError.value = ''
  if (!form.customer_id) {
    productLoading.value = false
    return
  }
  productLoading.value = true
  try {
    const result = await queryPlanProducts(form.customer_id, keyword)
    if (active && sequence === searchSequence) products.value = result
  } catch (error) {
    if (active && sequence === searchSequence) productError.value = getApiErrorDetail(error)?.message || '产品列表加载失败'
  } finally {
    if (active && sequence === searchSequence) productLoading.value = false
  }
}

function changeCustomer() {
  form.items = []
  selectedProducts.value = []
  void searchProducts()
}

function chooseProducts(ids: number[]) {
  const previous = new Map(form.items.map(item => [item.product_id, item]))
  selectedProducts.value = options.value.filter(item => ids.includes(item.id))
  form.items = ids.map(product_id => previous.get(product_id)
    ?? { product_id, order_quantity: 1, production_quantity: 1 })
}
function productLabel(id: number) {
  const item = selectedProducts.value.find(product => product.id === id)
  return item ? `${item.factory_code} · ${item.product_name}` : String(id)
}

async function save() {
  if (disabled.value || customerLoading.value || productLoading.value || customerError.value || productError.value) return
  if (!form.customer_id || !form.order_no.trim() || !form.items.length
    || form.items.some(item => !Number.isInteger(item.order_quantity) || item.order_quantity < 1
      || item.order_quantity > 2147483647 || !Number.isInteger(item.production_quantity)
      || item.production_quantity < 1 || item.production_quantity > 2147483647)) {
    ElMessage.warning('请填写客户、订单号，并为每个产品填写有效订单数量和生产数量')
    return
  }
  saving.value = true
  emit('busy', true)
  const input: ProductionPlanInput = {
    customer_id: form.customer_id, order_no: form.order_no.trim(),
    items: form.items.map(item => ({ ...item })),
  }
  try {
    await savePlan(input, props.plan)
    if (!active) return
    ElMessage.success(props.plan ? '生产计划已保存' : '生产计划已创建')
    emit('saved')
  } catch (error) {
    if (active) ElMessage.error(getApiErrorDetail(error)?.message || '生产计划保存失败')
  } finally {
    saving.value = false
    emit('busy', false)
  }
}

onMounted(() => {
  if (!props.readonly) {
    void loadCustomers()
    void searchProducts()
  }
})
onBeforeUnmount(() => { active = false; searchSequence += 1 })
</script>

<template>
  <ElForm label-position="top" :disabled="disabled" @submit.prevent="save">
    <LoadErrorAlert :message="customerError" :loading="customerLoading" @retry="loadCustomers" />
    <LoadErrorAlert :message="productError" :loading="productLoading" @retry="searchProducts()" />
    <div class="plan-form">
      <ElFormItem label="客户" required>
        <span v-if="readonly">{{ plan?.customer_name }}</span>
        <ElSelect v-else v-model="form.customer_id" filterable :loading="customerLoading" placeholder="选择客户" @change="changeCustomer">
          <ElOption v-for="item in customers" :key="item.id" :label="item.customer_name" :value="item.id" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="订单号" required>
        <span v-if="readonly">{{ form.order_no }}</span>
        <ElInput v-else v-model="form.order_no" maxlength="200" placeholder="填写订单号" />
      </ElFormItem>
    </div>
    <ElFormItem v-if="!readonly" label="产品（可多选）" required>
      <ElSelect :model-value="selectedIds" multiple filterable remote :remote-method="searchProducts" :loading="productLoading" :disabled="!form.customer_id || customerLoading" placeholder="选择该客户的多个产品" @change="chooseProducts">
        <ElOption v-for="item in options" :key="item.id" :label="`${item.factory_code} · ${item.product_name}`" :value="item.id" />
      </ElSelect>
    </ElFormItem>
    <section v-for="item in form.items" :key="item.product_id" class="product-item">
      <RouterLink v-if="readonly" :to="`/products/${item.product_id}?mode=view`">{{ productLabel(item.product_id) }}</RouterLink>
      <h3 v-else>{{ productLabel(item.product_id) }}</h3>
      <div class="plan-form">
        <ElFormItem label="订单数量" required>
          <span v-if="readonly">{{ item.order_quantity }}</span>
          <ElInputNumber v-else v-model="item.order_quantity" :min="1" :max="2147483647" :precision="0" />
        </ElFormItem>
        <ElFormItem label="生产数量" required>
          <span v-if="readonly">{{ item.production_quantity }}</span>
          <ElInputNumber v-else v-model="item.production_quantity" :min="1" :max="2147483647" :precision="0" />
        </ElFormItem>
      </div>
    </section>
    <p class="plan-note">计划不绑定产品版本。{{ readonly ? '部门安排数量不随工程修改自动重算。' : '保存时按正式路线生成部门工单。配件任务数为生产数量 × BOM 用量；激光或装配汇合后的装配体按生产数量安排。' }}</p>
    <ElButton v-if="!readonly" type="primary" native-type="submit" :loading="saving" :disabled="customerLoading || productLoading || !!customerError || !!productError">保存生产计划</ElButton>
  </ElForm>
</template>

<style scoped>
.plan-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 20px; }
.el-select { width: 100%; }
.product-item { margin-bottom: 16px; padding: 12px; border: 1px solid var(--erp-border); border-radius: 6px; }
.product-item h3 { margin: 0 0 12px; font-size: 15px; overflow-wrap: anywhere; }
.plan-note { margin: 0 0 20px; color: var(--erp-text-secondary); line-height: 1.6; }
@media (max-width: 640px) { .plan-form { grid-template-columns: 1fr; } }
</style>
