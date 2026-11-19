<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryProductVersions, type ProductVersionChoice } from '@/features/process-designer'
import { queryCustomers, type Customer } from '@/features/customers'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import PlanProductSnapshot from './PlanProductSnapshot.vue'
import { queryPlanProducts, savePlan, type PlanProduct } from '../api/plans'
import type { ProductionPlan, ProductionPlanInput, ProductionPlanItemInput } from '../domain/types'

const props = defineProps<{ plan?: ProductionPlan; readonly?: boolean }>()
const emit = defineEmits<{ saved: []; busy: [value: boolean] }>()
const customers = ref<Customer[]>([])
const products = ref<PlanProduct[]>([])
const appearanceVersions = ref<Record<number, ProductVersionChoice[]>>({})
const versionLoading = ref(false)
const versionError = ref('')
let versionSequence = 0
const customerLoading = ref(false)
const productLoading = ref(false)
const saving = ref(false)
const snapshotProductId = ref<number>()
function closeSnapshot(visible: boolean) { if (!visible) snapshotProductId.value = undefined }
const customerError = ref('')
const productError = ref('')
let active = true
let searchSequence = 0
const form = reactive({
  customer_id: props.plan?.customer_id as number | undefined,
  order_no: props.plan?.order_no || '',
  order_date: props.plan?.order_date || '',
  delivery_date: props.plan?.delivery_date || '',
  items: props.plan?.items.map(item => ({ product_id: item.product_id,
    order_quantity: item.order_quantity, production_quantity: item.production_quantity, source_version: item.source_version })) ?? [] as ProductionPlanItemInput[],
})
const selectedProducts = ref<PlanProduct[]>(props.plan?.items.map(item => ({
  id: item.product_id, customer_id: props.plan!.customer_id, version: item.source_version,
  version_value: item.source_version_value,
  product_name: item.product_name, factory_code: item.factory_code,
})) ?? [])
const selectedIds = computed(() => form.items.map(item => item.product_id))
const options = computed(() => {
  const byId = new Map([...products.value, ...selectedProducts.value].map(item => [item.id, item]))
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

async function loadAppearanceVersions() {
  const current = ++versionSequence
  versionLoading.value = true
  versionError.value = ''
  try {
    const values = await Promise.all(selectedIds.value.map(async id => [id, await queryProductVersions(id)] as const))
    if (active && current === versionSequence) appearanceVersions.value = Object.fromEntries(values)
  } catch (cause) {
    if (active && current === versionSequence) versionError.value = getApiErrorDetail(cause)?.message || '外观版本加载失败'
  } finally { if (active && current === versionSequence) versionLoading.value = false }
}

function changeCustomer() {
  form.items = []
  selectedProducts.value = []
  versionSequence += 1
  versionLoading.value = false
  versionError.value = ''
  appearanceVersions.value = {}
  void searchProducts()
}

function chooseProducts(ids: number[]) {
  const previous = new Map(form.items.map(item => [item.product_id, item]))
  selectedProducts.value = options.value.filter(item => ids.includes(item.id))
  form.items = ids.map(product_id => previous.get(product_id)
    ?? { product_id, order_quantity: 1, production_quantity: 1, source_version: options.value.find(item => item.id === product_id)?.version })
  void loadAppearanceVersions()
}
function productLabel(id: number) {
  const item = selectedProducts.value.find(product => product.id === id)
  return item ? `${item.factory_code} · ${item.product_name}` : String(id)
}

function productVersionValue(id: number) {
  return selectedProducts.value.find(item => item.id === id)?.version_value
}

async function save() {
  if (disabled.value || customerLoading.value || productLoading.value || versionLoading.value || customerError.value || productError.value || versionError.value) return
  if (!form.customer_id || !form.order_no.trim() || !form.items.length
    || form.items.some(item => !Number.isInteger(item.order_quantity) || item.order_quantity < 1
      || item.order_quantity > 2147483647 || !Number.isInteger(item.production_quantity)
      || item.production_quantity < 1 || item.production_quantity > 2147483647)) {
    ElMessage.warning('请填写客户、订单号，并为每个产品填写有效订单数量和生产数量')
    return
  }
  if (!form.order_date || !form.delivery_date || form.delivery_date < form.order_date) {
    ElMessage.warning('请填写下单日期和交货日期，交货日期不能早于下单日期')
    return
  }
  saving.value = true
  emit('busy', true)
  const input: ProductionPlanInput = {
    customer_id: form.customer_id, order_no: form.order_no.trim(),
    order_date: form.order_date, delivery_date: form.delivery_date,
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
    void loadAppearanceVersions()
  }
})
onBeforeUnmount(() => { active = false; searchSequence += 1; versionSequence += 1 })
</script>

<template>
  <ElForm label-position="top" :disabled="disabled" @submit.prevent="save">
    <LoadErrorAlert :message="customerError" :loading="customerLoading" @retry="loadCustomers" />
    <LoadErrorAlert :message="productError" :loading="productLoading" @retry="searchProducts()" />
    <LoadErrorAlert :message="versionError" :loading="versionLoading" @retry="loadAppearanceVersions" />
    <section class="form-section">
      <header class="form-section-heading"><span>01</span><div><h3>订单资料</h3></div></header>
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
      <ElFormItem label="下单日期" required>
        <span v-if="readonly">{{ form.order_date }}</span>
        <ElDatePicker v-else v-model="form.order_date" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" placeholder="选择下单日期" />
      </ElFormItem>
      <ElFormItem label="交货日期" required>
        <span v-if="readonly">{{ form.delivery_date }}</span>
        <ElDatePicker v-else v-model="form.delivery_date" type="date" value-format="YYYY-MM-DD" format="YYYY-MM-DD" placeholder="选择交货日期" />
      </ElFormItem>
    </div>
    </section>
    <section class="form-section">
      <header class="form-section-heading"><span>02</span><div><h3>产品与数量</h3></div></header>
    <ElFormItem v-if="!readonly" label="产品（可多选）" required>
      <ElSelect :model-value="selectedIds" multiple filterable remote :remote-method="searchProducts" :loading="productLoading" :disabled="!form.customer_id || customerLoading" placeholder="选择该客户的多个产品" @change="chooseProducts">
        <ElOption v-for="item in options" :key="item.id" :label="`${item.factory_code} · ${item.product_name}`" :value="item.id" />
      </ElSelect>
    </ElFormItem>
    <section v-for="(item, index) in form.items" :key="item.product_id" class="product-item">
      <span class="line-number">明细 {{ String(index + 1).padStart(2, '0') }}</span>
      <div v-if="readonly"><h3>{{ productLabel(item.product_id) }}</h3><button type="button" class="snapshot-link" @click="snapshotProductId = item.product_id">查看计划产品快照</button></div>
      <h3 v-else>{{ productLabel(item.product_id) }}</h3>
      <ElFormItem v-if="!readonly" label="外观版本" required>
        <ElSelect v-model="item.source_version" :loading="versionLoading" :disabled="versionLoading || !!versionError" placeholder="选择创建快照的外观版本">
          <ElOption v-for="version in appearanceVersions[item.product_id] || []" :key="version.version" :value="version.version" :label="version.value" />
        </ElSelect>
      </ElFormItem>
      <p v-else class="snapshot-source">{{ productVersionValue(item.product_id) }}</p>
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
    <ElEmpty v-if="!form.items.length" :image-size="64" />
    </section>
    <footer v-if="!readonly" class="form-submit">
    <ElButton v-if="!readonly" type="primary" native-type="submit" :loading="saving" :disabled="customerLoading || productLoading || versionLoading || !!customerError || !!productError || !!versionError">保存生产计划</ElButton></footer>
  </ElForm>
  <ElDialog :model-value="snapshotProductId !== undefined" @update:model-value="closeSnapshot" title="计划产品快照" width="min(1120px, 96vw)" destroy-on-close>
    <PlanProductSnapshot v-if="snapshotProductId && plan" :key="`${plan.id}:${snapshotProductId}`" :plan-id="plan.id" :product-id="snapshotProductId" />
  </ElDialog>
</template>

<style scoped>
.plan-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
.el-select { width: 100%; }
.product-item { margin-bottom: 16px; padding: 24px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface-muted); }
.product-item h3 { margin: 0 0 12px; font-size: 16px; overflow-wrap: anywhere; }

@media (max-width: 640px) { .plan-form { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .product-item { padding: 16px; } }
.form-section + .form-section { margin-top: 24px; padding-top: 24px; border-top: 1px solid var(--erp-border); }
.form-section-heading { display: flex; gap: 12px; margin-bottom: 24px; align-items: flex-start; }
.form-section-heading > span { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 8px; background: var(--erp-primary-soft); color: var(--erp-primary); font-size: 12px; font-weight: 600; }
.form-section-heading h3 { margin: 0; font-size: 16px; font-weight: 600; }
.line-number { display: block; margin-bottom: 8px; font-size: 11px; color: var(--erp-text-muted); }.product-item :deep(.el-input-number) { width: 100%; }.product-item .plan-form { margin-top: 16px; }

.form-submit { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; padding-top: 24px; border-top: 1px solid var(--erp-border); }
.snapshot-source { font-size: 12px; color: var(--erp-text-muted); }
.snapshot-link { min-height: 44px; padding: 8px 0; border: 0; background: transparent; color: var(--erp-primary); font: inherit; font-size: 14px; cursor: pointer; }
</style>
