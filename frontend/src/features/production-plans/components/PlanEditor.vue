<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryCustomers, type Customer } from '@/features/customers'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { queryPlanProducts, savePlan, type PlanProduct } from '../api/plans'
import type { ProductionPlan, ProductionPlanInput } from '../domain/types'

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
  order_quantity: props.plan?.order_quantity ?? 1,
  product_id: props.plan?.product_id as number | undefined,
  production_quantity: props.plan?.production_quantity ?? 1,
})
const selectedProduct = ref<PlanProduct | undefined>(props.plan ? {
  id: props.plan.product_id,
  customer_id: props.plan.customer_id,
  product_name: props.plan.product_name,
  factory_code: props.plan.factory_code,
} : undefined)
const options = computed(() => {
  const selected = selectedProduct.value
  return selected && !products.value.some(item => item.id === selected.id)
    ? [selected, ...products.value] : products.value
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
  form.product_id = undefined
  selectedProduct.value = undefined
  void searchProducts()
}

function chooseProduct(id: number) {
  selectedProduct.value = options.value.find(item => item.id === id)
}

async function save() {
  if (disabled.value || customerLoading.value || productLoading.value || customerError.value || productError.value) return
  if (!form.customer_id || !form.product_id || !form.order_no.trim()
    || !Number.isInteger(form.order_quantity) || form.order_quantity < 1
    || !Number.isInteger(form.production_quantity) || form.production_quantity < 1) {
    ElMessage.warning('请完整填写客户、订单号、订单数量、产品和生产数量')
    return
  }
  saving.value = true
  emit('busy', true)
  const input: ProductionPlanInput = {
    customer_id: form.customer_id, order_no: form.order_no.trim(),
    order_quantity: form.order_quantity, product_id: form.product_id,
    production_quantity: form.production_quantity,
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
      <ElFormItem label="订单数量" required>
        <span v-if="readonly">{{ form.order_quantity }}</span>
        <ElInputNumber v-else v-model="form.order_quantity" :min="1" :max="2147483647" :precision="0" />
      </ElFormItem>
      <ElFormItem label="产品" required>
        <RouterLink v-if="readonly && plan" :to="`/products/${plan.product_id}?mode=view`">{{ plan.factory_code }} · {{ plan.product_name }}</RouterLink>
        <ElSelect v-else v-model="form.product_id" filterable remote :remote-method="searchProducts" :loading="productLoading" :disabled="!form.customer_id || customerLoading" placeholder="选择该客户的产品" @change="chooseProduct">
          <ElOption v-for="item in options" :key="item.id" :label="`${item.factory_code} · ${item.product_name}`" :value="item.id" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="生产数量" required>
        <span v-if="readonly">{{ form.production_quantity }}</span>
        <ElInputNumber v-else v-model="form.production_quantity" :min="1" :max="2147483647" :precision="0" />
      </ElFormItem>
    </div>
    <p class="plan-note">计划不绑定产品版本。{{ readonly ? '部门安排数量不随工程修改自动重算。' : '保存时按正式路线生成部门工单。配件任务数为生产数量 × BOM 用量；激光或装配汇合后的装配体按生产数量安排。' }}</p>
    <ElButton v-if="!readonly" type="primary" native-type="submit" :loading="saving" :disabled="customerLoading || productLoading || !!customerError || !!productError">保存生产计划</ElButton>
  </ElForm>
</template>

<style scoped>
.plan-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 20px; }
.plan-form :deep(.el-select) { width: 100%; }
.plan-note { margin: 0 0 20px; color: var(--erp-text-secondary); line-height: 1.6; }
@media (max-width: 640px) { .plan-form { grid-template-columns: 1fr; } }
</style>
