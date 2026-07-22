<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import BomEditor from '../components/BomEditor.vue'
import ProcessFlowEditor from '../components/ProcessFlowEditor.vue'
import { type BomItem, type ProductFields } from '../domain/types'
import { useEngineeringProductsStore } from '../stores/engineeringProducts'
import { useAuthStore } from '@/stores/auth'
import { PRODUCT_PERMISSIONS } from '@/permission/constants'
import { useProductEditorForm } from '../composables/useProductEditorForm'
import { useProductSaveActions, type FlowEditorApi } from '../composables/useProductSaveActions'
import { useUnsavedChangesGuard } from '../composables/useUnsavedChangesGuard'
import { useProductVersionLoader } from '../composables/useProductVersionLoader'
import { useProductVersionActions } from '../composables/useProductVersionActions'
import { queryCustomers, type Customer } from '@/features/customers/api/customers'

const route = useRoute()
const router = useRouter()
const store = useEngineeringProductsStore()
const authStore = useAuthStore()
const baseFormRef = ref<FormInstance>()
const flowEditor = ref<FlowEditorApi>()
const editorReady = ref(false)
const customers = ref<Customer[]>([])
const customerLoading = ref(false)
const {
  applyProduct,
  bomDirty,
  bomSnapshot,
  flowDirty,
  flowSnapshot,
  form,
  markSaved,
  normalizedBom,
  normalizedFields,
  validateBom,
  versionDirty: rawVersionDirty,
} = useProductEditorForm()

const productId = computed(() => {
  const value = Number(route.params.productId)
  return Number.isInteger(value) && value > 0 ? value : null
})
const mode = computed(() => route.query.mode === 'view' ? 'view' : 'edit')
const canEditProduct = computed(() => authStore.hasPermission(PRODUCT_PERMISSIONS.edit))
const baseReadOnly = computed(() => Boolean(productId.value))

const baseRules: FormRules<ProductFields> = {
  customer_name: [{ required: true, whitespace: true, message: '请输入客户名称', trigger: 'blur' }],
  product_name: [{ required: true, whitespace: true, message: '请输入产品名称', trigger: 'blur' }],
  factory_code: [{ required: true, whitespace: true, message: '请输入本厂型号', trigger: 'blur' }],
  customer_code: [{ required: true, whitespace: true, message: '请输入客户型号', trigger: 'blur' }],
}

const customerSelection = computed(() => form.customer_id ?? form.customer_name)

function selectCustomer(value: number | string) {
  if (typeof value === 'number') {
    const customer = customers.value.find(item => item.id === value)
    form.customer_id = value
    form.customer_name = customer?.customer_name || ''
  } else {
    form.customer_id = null
    form.customer_name = value.trim()
  }
}

async function loadCustomers() {
  customerLoading.value = true
  try {
    customers.value = await queryCustomers()
  } finally {
    customerLoading.value = false
  }
}

async function validateBase() {
  try {
    await baseFormRef.value?.validate()
    return true
  } catch {
    return false
  }
}

const { clearFlowSaveError, createProduct, flowSaveError, saveBom, saveFlow } = useProductSaveActions({
  applyProduct,
  bomSnapshot,
  editorReady,
  flowEditor,
  flowSnapshot,
  form,
  markSaved,
  normalizedBom,
  normalizedFields,
  productId,
  router,
  store,
  validateBase,
  validateBom,
})
watch(() => form.version, clearFlowSaveError)

const {
  baseInfoEditable,
  currentVersion,
  loadProductVersion,
  loadingProduct,
  reloadVersions,
  switchVersion,
  versionEditable,
  versions,
} = useProductVersionLoader({
  applyProduct,
  editorReady,
  markSaved,
  mode,
  productId,
  router,
  store,
  versionDirty: rawVersionDirty,
})
const selectedVersion = computed(() => form.version || currentVersion.value)
const versionDirty = computed(() => !loadingProduct.value && rawVersionDirty.value)
const versionReadOnly = computed(() => Boolean(
  mode.value === 'view'
  || !canEditProduct.value
  || !versionEditable.value,
))

function updateBom(items: BomItem[]) {
  const nextIds = new Set(items.flatMap((item) => item.id ? [item.id] : []))
  const removedReferencedItem = form.bom_items.find((item) =>
    item.id
    && !nextIds.has(item.id)
    && form.process_flow.nodes.some(
      (node) => node.type === 'part' && node.bom_item_id === item.id,
    ),
  )
  if (removedReferencedItem) {
    ElMessage.warning(`“${removedReferencedItem.part_name}”已被流程图引用，请先删除对应配件节点`)
    return
  }
  form.bom_items = items
}

useUnsavedChangesGuard(versionDirty)

const { createVersion, deleteSelectedVersion, enterEditMode, returnViewMode } = useProductVersionActions({
  form,
  loadProductVersion,
  productId,
  reloadVersions,
  router,
  selectedVersion,
  store,
  versionDirty,
})

onMounted(async () => {
  await loadCustomers()
  if (!productId.value) {
    markSaved(['base', 'bom', 'flow'])
    return
  }
  try {
    await reloadVersions()
    const requestedVersion = Number(route.query.version)
    await loadProductVersion(Number.isInteger(requestedVersion) && requestedVersion > 0
      ? requestedVersion
      : undefined)
  } catch {
    ElMessage.error('产品不存在或加载失败')
    router.replace('/products')
  }
})
</script>

<template>
  <main class="editor-page">
    <header class="editor-header">
      <div>
        <div class="page-kicker">工程部 / {{ productId ? mode === 'view' ? '查看产品' : '编辑产品' : '录入产品' }}</div>
        <h1>{{ productId ? form.product_name || (mode === 'view' ? '查看产品' : '编辑产品') : '录入新产品' }}</h1>
      </div>
      <div class="editor-actions">
        <ElSelect
          v-if="productId"
          :model-value="form.version"
          placement="top-start"
          :fallback-placements="['top-start', 'top-end']"
          style="width: 110px"
          @change="switchVersion"
        >
          <ElOption v-for="version in versions" :key="version" :label="`V${version}`" :value="version" />
        </ElSelect>
        <ElButton
          v-if="productId && mode === 'view' && canEditProduct"
          type="primary"
          plain
          @click="enterEditMode"
        >进入编辑</ElButton>
        <ElButton
          v-if="productId && mode === 'edit'"
          plain
          @click="returnViewMode"
        >返回查看</ElButton>
        <ElButton
          type="primary"
          v-if="productId && mode === 'edit' && canEditProduct"
          :loading="store.saving"
          @click="createVersion"
        >基于此版本创建新版</ElButton>
        <ElButton
          v-if="productId && mode === 'edit'"
          v-permission="PRODUCT_PERMISSIONS.delete"
          type="danger"
          plain
          :loading="store.saving"
          @click="deleteSelectedVersion"
        >删除当前版本</ElButton>
        <ElButton @click="router.push('/products')">返回列表</ElButton>
        <ElButton
          v-if="!productId"
          type="primary"
          :loading="store.saving"
          @click="createProduct"
        >保存并继续配置流程</ElButton>
      </div>
    </header>

    <section class="editor-card basic-section">
      <div class="section-heading">
        <div>
          <h2>产品基础信息</h2>
          <span>产品级资料，所有版本共享；创建订单后不可修改。</span>
        </div>
      </div>
      <ElAlert
        v-if="productId && !baseInfoEditable"
        class="section-alert"
        title="产品基础信息为共享资料，已有订单引用后固定为只读。"
        type="info"
        :closable="false"
      />
      <ElForm ref="baseFormRef" :model="form" :rules="baseRules" :disabled="baseReadOnly" label-position="top">
        <div class="form-grid">
          <ElFormItem prop="factory_code" label="厂编"><ElInput v-model="form.factory_code" /></ElFormItem>
          <ElFormItem prop="product_name" label="产品名称"><ElInput v-model="form.product_name" /></ElFormItem>
          <ElFormItem prop="customer_name" label="客户名称">
            <ElSelect
              :model-value="customerSelection"
              placement="top-start"
              :fallback-placements="['top-start', 'top-end']"
              filterable
              allow-create
              default-first-option
              :loading="customerLoading"
              placeholder="选择已有客户或输入新客户"
              style="width: 100%"
              @change="selectCustomer"
            >
              <ElOption
                v-for="customer in customers"
                :key="customer.id"
                :label="customer.customer_name"
                :value="customer.id"
              />
            </ElSelect>
          </ElFormItem>
          <ElFormItem prop="customer_code" label="客编"><ElInput v-model="form.customer_code" /></ElFormItem>
        </div>
      </ElForm>
    </section>

    <section class="editor-card">
      <div class="section-action">
        <ElButton v-if="productId && !versionReadOnly" type="primary" plain :disabled="!bomDirty" :loading="store.saving" @click="saveBom">保存 BOM</ElButton>
      </div>
      <ElAlert
        v-if="productId && mode === 'edit' && !versionEditable"
        class="section-alert"
        title="当前版本已被订单或生产记录引用，BOM 不可修改。请基于此版本创建新版后修改。"
        type="warning"
        :closable="false"
      />
      <div><BomEditor :model-value="form.bom_items" :readonly="versionReadOnly" @update:model-value="updateBom" /></div>
    </section>

    <section class="editor-card">
      <ElAlert v-if="!productId" title="请先保存产品基础信息和 BOM，再配置工序流程" type="info" :closable="false" show-icon />
      <template v-else-if="editorReady">
        <ElAlert v-if="mode === 'view'" title="查看模式为只读" type="info" :closable="false" />
        <ElAlert
          v-else-if="!versionEditable"
          title="当前版本已被订单或生产记录引用，工序流程不可修改。请基于此版本创建新版后修改。"
          type="warning"
          :closable="false"
        />
        <div v-if="!versionReadOnly" class="section-action"><ElButton type="primary" plain :disabled="!flowDirty" :loading="store.saving" @click="saveFlow">保存工序流程</ElButton></div>
        <ProcessFlowEditor
          ref="flowEditor"
          v-model="form.process_flow"
          :bom-items="form.bom_items"
          :readonly="versionReadOnly"
          @update:model-value="clearFlowSaveError"
        />
      </template>
      <div v-else v-loading="true" class="flow-loading">正在加载流程图</div>
    </section>
  </main>
</template>

<style scoped>
.editor-page { min-height: 100vh; padding: 24px; background: var(--erp-bg); }
.editor-header, .editor-card { border: 1px solid var(--erp-border); border-radius: 10px; background: #fff; box-shadow: var(--erp-shadow-sm); }
.editor-header { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 18px; padding: 18px 22px; }
.editor-header h1 { margin: 5px 0 0; font-size: 23px; }
.editor-actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }
.editor-actions :deep(.el-button + .el-button) { margin-left: 0; }
.page-kicker { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.editor-card { margin-bottom: 18px; padding: 20px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-heading > div { display: flex; align-items: baseline; gap: 12px; }
.section-heading h2 { margin: 0; font-size: 18px; }
.section-heading span { color: var(--el-text-color-secondary); font-size: 12px; }
.section-action { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.flow-error { margin-bottom: 12px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 20px; }
.basic-section :deep(.el-form-item) { margin-bottom: 12px; }
.flow-loading { display: grid; min-height: 260px; place-items: center; color: var(--el-text-color-secondary); }
.read-only-content { pointer-events: none; opacity: .82; }
@media (max-width: 680px) { .editor-page { padding: 12px; } .editor-header { align-items: flex-start; flex-direction: column; } .form-grid { grid-template-columns: 1fr; } }
</style>
