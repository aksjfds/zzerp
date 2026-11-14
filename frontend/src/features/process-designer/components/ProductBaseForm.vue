<script setup lang="ts">
import { computed, onMounted } from 'vue'
import type { FormRules } from 'element-plus'
import { queryCustomers, type Customer } from '@/features/customers'
import { useRequest } from '@/shared/query/useRequest'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import type { ProductFields } from '../domain/types'

const props = defineProps<{ modelValue: ProductFields; readonly: boolean; disabled: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: ProductFields] }>()
const request = useRequest<Customer[]>('客户列表加载失败')
const customers = computed(() => request.data.value ?? [])
const loading = request.loading, error = request.error
const selection = computed(() => props.modelValue.customer_id ?? props.modelValue.customer_name)
const rules: FormRules<ProductFields> = {
  customer_name: [{ required: true, whitespace: true, message: '请输入客户名称', trigger: 'blur' }],
  product_name: [{ required: true, whitespace: true, message: '请输入产品名称', trigger: 'blur' }],
  factory_code: [{ required: true, whitespace: true, message: '请输入厂编', trigger: 'blur' }],
  customer_code: [{ required: true, whitespace: true, message: '请输入客编', trigger: 'blur' }],
}
function loadCustomers() { return request.run(signal => queryCustomers(undefined, signal)) }
function update(field: keyof ProductFields, value: string | number | null) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
function selectCustomer(value: string | number) {
  const customer = typeof value === 'number' ? customers.value.find(item => item.id === value) : undefined
  emit('update:modelValue', {
    ...props.modelValue,
    customer_id: customer?.id ?? null,
    customer_name: customer?.customer_name ?? String(value).trim(),
  })
}
onMounted(() => { void loadCustomers() })
</script>

<template>
  <dl v-if="readonly" class="base-details">
    <div><dt>厂编</dt><dd>{{ modelValue.factory_code }}</dd></div>
    <div><dt>产品名称</dt><dd>{{ modelValue.product_name }}</dd></div>
    <div><dt>客户名称</dt><dd>{{ modelValue.customer_name }}</dd></div>
    <div><dt>客编</dt><dd>{{ modelValue.customer_code }}</dd></div>
  </dl>
  <template v-else>
    <LoadErrorAlert :message="error" :loading="loading" @retry="loadCustomers" />
    <ElForm :model="modelValue" :rules="rules" :disabled="disabled" label-position="top">
      <div class="base-grid">
        <ElFormItem prop="factory_code" label="厂编"><ElInput :model-value="modelValue.factory_code" @update:model-value="update('factory_code', $event)" /></ElFormItem>
        <ElFormItem prop="product_name" label="产品名称"><ElInput :model-value="modelValue.product_name" @update:model-value="update('product_name', $event)" /></ElFormItem>
        <ElFormItem prop="customer_name" label="客户名称">
          <ElSelect :model-value="selection" filterable allow-create default-first-option :loading="loading" :disabled="loading || !!error" @change="selectCustomer">
            <ElOption v-for="customer in customers" :key="customer.id" :label="customer.customer_name" :value="customer.id" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem prop="customer_code" label="客编"><ElInput :model-value="modelValue.customer_code" @update:model-value="update('customer_code', $event)" /></ElFormItem>
      </div>
    </ElForm>
  </template>
</template>

<style scoped>
.base-grid, .base-details { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 20px; }
.base-details { margin: 0; gap: 18px 24px; }
.base-details dt { color: var(--erp-text-secondary); font-size: 13px; }
.base-details dd { margin: 6px 0 0; overflow-wrap: anywhere; }
.el-select { width: 100%; }
@media (max-width: 640px) { .base-grid, .base-details { grid-template-columns: 1fr; } }
</style>
