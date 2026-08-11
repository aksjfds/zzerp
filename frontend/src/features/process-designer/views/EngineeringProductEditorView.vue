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
const activeAction = ref<
  'create' | 'base' | 'bom' | 'flow-draft' | 'flow' | 'version-create' | 'version-delete' | null
>(null)

async function performAction(action: NonNullable<typeof activeAction.value>, callback: () => Promise<unknown>) {
  if (activeAction.value) return
  activeAction.value = action
  try {
    await callback()
  } finally {
    activeAction.value = null
  }
}
const {
  allDirty,
  applyProduct,
  baseDirty,
  bomDirty,
  bomSnapshot,
  flowDirty,
  flowSnapshot,
  form,
  markSaved,
  normalizedBom,
  normalizedFields,
  validateBom,
} = useProductEditorForm()

const productId = computed(() => {
  const value = Number(route.params.productId)
  return Number.isInteger(value) && value > 0 ? value : null
})
const mode = computed(() => route.query.mode === 'view' ? 'view' : 'edit')
const canEditProduct = computed(() => authStore.hasPermission(PRODUCT_PERMISSIONS.edit))

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

const {
  clearFlowSaveError,
  createProduct,
  flowSaveError,
  saveBom,
  saveFlow,
  saveFlowDraft,
  saveProductInfo,
} = useProductSaveActions({
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
  versionDirty: allDirty,
})
const selectedVersion = computed(() => form.version || currentVersion.value)
const pageDirty = computed(() => !loadingProduct.value && allDirty.value)
const baseReadOnly = computed(() => Boolean(
  mode.value === 'view'
  || !canEditProduct.value
  || !baseInfoEditable.value
  || store.saving,
))
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

useUnsavedChangesGuard(pageDirty)

const { createVersion, deleteSelectedVersion, enterEditMode, returnViewMode } = useProductVersionActions({
  form,
  loadProductVersion,
  productId,
  reloadVersions,
  router,
  selectedVersion,
  store,
  versionDirty: pageDirty,
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
        <div v-if="productId" class="version-selector">
          <span>当前版本</span>
          <ElSelect
            :model-value="form.version"
            :disabled="store.saving"
            placement="top-start"
            :fallback-placements="['top-start', 'top-end']"
            @change="switchVersion"
          >
            <ElOption v-for="version in versions" :key="version" :label="`V${version}`" :value="version" />
          </ElSelect>
        </div>
        <div class="action-group navigation-actions">
          <ElButton :disabled="store.saving" @click="router.push('/products')">返回产品列表</ElButton>
          <ElButton
            v-if="productId && mode === 'view' && canEditProduct"
            type="primary"
            @click="enterEditMode"
          >进入编辑</ElButton>
          <ElButton
            v-if="productId && mode === 'edit'"
            :disabled="store.saving"
            @click="returnViewMode"
          >退出编辑</ElButton>
        </div>
        <div v-if="productId && mode === 'edit' && canEditProduct" class="action-group version-actions">
          <ElButton
            type="primary"
            plain
            :disabled="store.saving"
            :loading="activeAction === 'version-create'"
            @click="performAction('version-create', createVersion)"
          >创建新版本</ElButton>
          <ElButton
            v-permission="PRODUCT_PERMISSIONS.delete"
            type="danger"
            plain
            :disabled="store.saving"
            :loading="activeAction === 'version-delete'"
            @click="performAction('version-delete', deleteSelectedVersion)"
          >删除此版本</ElButton>
        </div>
        <ElButton
          v-if="!productId"
          type="primary"
          :disabled="store.saving"
          :loading="activeAction === 'create'"
          @click="performAction('create', createProduct)"
        >保存产品并配置流程</ElButton>
      </div>
    </header>

    <section class="editor-card basic-section">
      <div class="section-heading">
        <div>
          <h2>产品基础信息</h2>
          <span>产品级资料，所有版本共享；创建订单后不可修改。</span>
        </div>
        <ElButton
          v-if="productId && mode === 'edit' && canEditProduct && baseInfoEditable"
          type="primary"
          :disabled="!baseDirty || store.saving"
          :loading="activeAction === 'base'"
          @click="performAction('base', saveProductInfo)"
        >保存基础信息</ElButton>
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
      <ElAlert
        v-if="productId && mode === 'edit' && !versionEditable"
        class="section-alert"
        title="当前版本已被订单或生产记录引用，BOM 不可修改。请基于此版本创建新版后修改。"
        type="warning"
        :closable="false"
      />
      <BomEditor
        :model-value="form.bom_items"
        :readonly="versionReadOnly"
        :can-save="Boolean(productId && !versionReadOnly)"
        :dirty="bomDirty"
        :saving="activeAction === 'bom'"
        @update:model-value="updateBom"
        @save="performAction('bom', saveBom)"
      />
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
        <ElAlert
          v-if="flowSaveError"
          class="flow-error"
          :title="flowSaveError.message"
          type="error"
          :closable="false"
          show-icon
        />
        <ProcessFlowEditor
          ref="flowEditor"
          v-model="form.process_flow"
          :bom-items="form.bom_items"
          :readonly="versionReadOnly"
          @update:model-value="clearFlowSaveError"
        >
          <template v-if="!versionReadOnly" #actions>
            <ElButton
              plain
              :disabled="!flowDirty || store.saving"
              :loading="activeAction === 'flow-draft'"
              @click="performAction('flow-draft', saveFlowDraft)"
            >保存草稿</ElButton>
            <ElButton
              type="primary"
              :disabled="(!flowDirty && !form.process_flow_is_draft) || store.saving"
              :loading="activeAction === 'flow'"
              @click="performAction('flow', saveFlow)"
            >确认并保存流程</ElButton>
          </template>
        </ProcessFlowEditor>
      </template>
      <div v-else v-loading="true" class="flow-loading">正在加载流程图</div>
    </section>
  </main>
</template>

<style scoped>
.editor-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--md-surface); }
.editor-header, .editor-card { border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.editor-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 18px; padding: 18px 22px; background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.editor-header h1 { margin: 5px 0 0; font-size: 24px; font-weight: 600; letter-spacing: -.02em; }
.editor-actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.action-group { display: flex; align-items: center; gap: 8px; }
.action-group + .action-group { padding-left: 8px; border-left: 1px solid var(--md-outline-variant); }
.editor-actions :deep(.el-button + .el-button), .action-group :deep(.el-button + .el-button) { margin-left: 0; }
.version-selector { display: flex; align-items: center; gap: 7px; margin-right: 2px; color: var(--el-text-color-secondary); font-size: 12px; white-space: nowrap; }
.version-selector :deep(.el-select) { width: 92px; }
.page-kicker { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.editor-card { margin-bottom: 18px; padding: 20px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-heading > div { display: flex; align-items: baseline; gap: 12px; }
.section-heading h2 { margin: 0; font-size: 18px; }
.section-heading span { color: var(--el-text-color-secondary); font-size: 12px; }
.flow-error { margin-bottom: 12px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 20px; }
.basic-section :deep(.el-form-item) { margin-bottom: 12px; }
.flow-loading { display: grid; min-height: 260px; place-items: center; color: var(--el-text-color-secondary); }
.read-only-content { pointer-events: none; opacity: .82; }
@media (max-width: 680px) {
  .editor-page { padding: 16px; }
  .editor-header { align-items: flex-start; flex-direction: column; padding: 16px; }
  .editor-actions { align-items: stretch; width: 100%; flex-direction: column; }
  .version-selector { justify-content: space-between; margin: 0; }
  .version-selector :deep(.el-select) { width: 120px; }
  .action-group { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); width: 100%; }
  .action-group + .action-group { padding: 8px 0 0; border-top: 1px solid var(--md-outline-variant); border-left: 0; }
  .editor-actions > :deep(.el-button), .action-group :deep(.el-button) { width: 100%; margin: 0; }
  .editor-card { padding: 16px; }
  .form-grid { grid-template-columns: 1fr; }
  .section-heading { align-items: flex-start; flex-direction: column; }
  .section-heading > div { align-items: flex-start; flex-direction: column; gap: 4px; }
}
@media (max-width: 440px) {
  .editor-page { padding: 12px; }
  .action-group { grid-template-columns: 1fr; }
  .editor-card { padding: 12px; }
}
</style>
