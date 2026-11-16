<script setup lang="ts">
import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import BomEditor from '../components/BomEditor.vue'
import ProcessFlowEditor from '../components/ProcessFlowEditor.vue'
import { type BomItem, type ProductForm } from '../domain/types'
import { useEngineeringProductsStore } from '../stores/engineeringProducts'
import { useAuthStore } from '@/stores/auth'
import { PRODUCT_PERMISSIONS } from '@/permission/constants'
import { useProductEditorForm } from '../composables/useProductEditorForm'
import { useProductSaveActions, type FlowEditorApi } from '../composables/useProductSaveActions'
import { useUnsavedChangesGuard } from '../composables/useUnsavedChangesGuard'
import { useProductVersionLoader } from '../composables/useProductVersionLoader'
import { useProductVersionActions } from '../composables/useProductVersionActions'
import { queryCustomers, type Customer } from '@/features/customers'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import PageHeader from '@/shared/layout/PageHeader.vue'

const route = useRoute()
const router = useRouter()
const store = useEngineeringProductsStore()
const authStore = useAuthStore()
const baseFormRef = ref<FormInstance>()
const flowEditor = ref<FlowEditorApi>()
const editorReady = ref(false)
const customers = ref<Customer[]>([])
const customerLoading = ref(false)
const customerError = ref('')
const initializationError = ref('')
const initializing = ref(false)
let customerRequest = 0
let initializationRequest = 0
const activeAction = ref<
  'create' | 'base' | 'bom' | 'flow-draft' | 'flow' | 'version-create' | null
>(null)

async function performAction(action: NonNullable<typeof activeAction.value>, callback: () => Promise<unknown>) {
  if (activeAction.value || !contentReady.value) return
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
  resetForm,
  validateBom,
} = useProductEditorForm()

const productId = computed(() => {
  const value = Number(route.params.productId)
  return Number.isInteger(value) && value > 0 ? value : null
})
const mode = computed(() => route.query.mode === 'view' ? 'view' : 'edit')
const canEditProduct = computed(() => authStore.hasPermission(PRODUCT_PERMISSIONS.edit))
const editableDirty = computed(() => mode.value === 'edit' && allDirty.value)

const baseRules: FormRules<ProductForm> = {
  version_value: [{ required: true, whitespace: true, message: '请输入外观版本', trigger: 'blur' },
    { max: 100, message: '外观版本不能超过100个字符', trigger: 'blur' }],
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
  const request = ++customerRequest
  customerLoading.value = true
  customerError.value = ''
  try {
    const result = await queryCustomers()
    if (request === customerRequest) customers.value = result
  } catch (error) {
    if (request === customerRequest) customerError.value = getApiErrorDetail(error)?.message || '客户列表加载失败'
  } finally {
    if (request === customerRequest) customerLoading.value = false
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
  productError,
  requestedVersion,
  retryProductVersion,
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
  versionDirty: editableDirty,
})
const selectedVersion = computed(() => form.version || currentVersion.value)
const contentReady = computed(() => !productId.value || (editorReady.value && !initializing.value && !loadingProduct.value && !initializationError.value))
const pageDirty = computed(() => contentReady.value && editableDirty.value)
const baseReadOnly = computed(() => Boolean(
  mode.value === 'view'
  || !canEditProduct.value
  || (productId.value && !baseInfoEditable.value)
  || !contentReady.value
  || store.saving,
))
const versionReadOnly = computed(() => Boolean(
  mode.value === 'view'
  || !canEditProduct.value
  || (productId.value && !versionEditable.value)
  || !contentReady.value,
))

function updateBom(items: BomItem[]) {
  form.bom_items = items
}

useUnsavedChangesGuard(pageDirty)

const { createVersion, enterEditMode, returnViewMode } = useProductVersionActions({
  form,
  loadProductVersion,
  productId,
  reloadVersions,
  router,
  selectedVersion,
  store,
  versionDirty: pageDirty,
})

async function initializeProduct() {
  const request = ++initializationRequest
  initializationError.value = ''
  if (!productId.value) {
    initializing.value = false
    resetForm()
    markSaved(['base', 'bom', 'flow'])
    return
  }
  initializing.value = true
  editorReady.value = false
  try {
    await reloadVersions()
    if (request !== initializationRequest) return
    const requestedVersion = Number(route.query.version)
    await loadProductVersion(Number.isInteger(requestedVersion) && requestedVersion > 0
      ? requestedVersion
      : undefined)
  } catch (error) {
    if (request === initializationRequest) initializationError.value = getApiErrorDetail(error)?.message || '产品外观版本列表加载失败'
  } finally {
    if (request === initializationRequest) initializing.value = false
  }
}

onMounted(() => {
  void loadCustomers()
  void initializeProduct()
})
watch(productId, () => { void initializeProduct() })
onScopeDispose(() => {
  customerRequest++
  initializationRequest++
})
</script>

<template>
  <main class="editor-page">
    <PageHeader class="editor-heading" section-name="工程资料" :page-title="productId ? contentReady ? form.product_name || '产品工程资料' : '产品工程资料' : '新建产品'">
      <template #actions>
      <div class="editor-actions">
        <div v-if="productId" class="version-selector">
          <span>当前外观版本</span>
          <ElSelect
            :model-value="requestedVersion ?? form.version"
            :disabled="store.saving || initializing || loadingProduct"
            :loading="initializing || loadingProduct"
            placement="top-start"
            :fallback-placements="['top-start', 'top-end']"
            @change="switchVersion"
          >
            <ElOption v-for="version in versions" :key="version.version" :label="version.value" :value="version.version" />
          </ElSelect>
        </div>
        <div class="action-group navigation-actions">
          <ElButton :disabled="store.saving" @click="router.push('/products')">返回产品列表</ElButton>
          <ElButton
            v-if="productId && mode === 'view' && canEditProduct"
            type="primary"
            :disabled="!contentReady"
            @click="enterEditMode"
          >进入编辑</ElButton>
          <ElButton
            v-if="productId && mode === 'edit'"
            :disabled="store.saving || !contentReady"
            @click="returnViewMode"
          >退出编辑</ElButton>
        </div>
        <div v-if="productId && mode === 'edit' && canEditProduct" class="action-group version-actions">
          <ElButton
            type="primary"
            plain
            :disabled="store.saving || !contentReady"
            :loading="activeAction === 'version-create'"
            @click="performAction('version-create', createVersion)"
          >创建新外观版本</ElButton>
        </div>
        <ElButton
          v-if="!productId"
          type="primary"
          :disabled="store.saving"
          :loading="activeAction === 'create'"
          @click="performAction('create', createProduct)"
        >保存产品并配置流程</ElButton>
      </div>
      </template>
    </PageHeader>

    <LoadErrorAlert :message="initializationError" :loading="initializing" @retry="initializeProduct" />
    <LoadErrorAlert :message="productError" :loading="loadingProduct" @retry="retryProductVersion" />
    <div v-if="productId && (initializing || loadingProduct)" class="editor-loading" role="status">
      <ElSkeleton :rows="6" animated />
      <p>正在加载产品资料与外观版本…</p>
    </div>
    <template v-if="contentReady">
      <nav class="editor-navigation" aria-label="工程资料章节">
        <a href="#product-basics"><span>01</span><div>基础资料<small v-if="baseDirty">有未保存修改</small></div></a>
        <a href="#product-bom"><span>02</span><div>物料清单<small>{{ bomDirty ? '有未保存修改' : `${form.bom_items.length} 项配件` }}</small></div></a>
        <a href="#product-process"><span>03</span><div>工艺路线<small v-if="flowDirty">有未保存修改</small></div></a>
      </nav>
      <section id="product-basics" class="editor-card basic-section">
        <div class="section-heading">
          <div>
            <h2>产品基础信息</h2>

          </div>
          <ElButton
            v-if="productId && mode === 'edit' && canEditProduct && baseInfoEditable"
            type="primary"
            :disabled="!baseDirty || store.saving"
            :loading="activeAction === 'base'"
            @click="performAction('base', saveProductInfo)"
          >保存基础信息</ElButton>
        </div>
        <LoadErrorAlert :message="customerError" :loading="customerLoading" @retry="loadCustomers" />
        <dl v-if="mode === 'view' || (productId && !baseInfoEditable)" class="base-details">
          <div><dt>厂编</dt><dd>{{ form.factory_code }}</dd></div>
          <div><dt>产品名称</dt><dd>{{ form.product_name }}</dd></div>
          <div><dt>客户名称</dt><dd>{{ form.customer_name }}</dd></div>
          <div><dt>客编</dt><dd>{{ form.customer_code }}</dd></div>
        </dl>
        <ElForm v-else ref="baseFormRef" :model="form" :rules="baseRules" :disabled="baseReadOnly" label-position="top">
          <div class="form-grid">
            <ElFormItem prop="factory_code" label="厂编"><ElInput v-model="form.factory_code" /></ElFormItem>
            <ElFormItem prop="product_name" label="产品名称"><ElInput v-model="form.product_name" /></ElFormItem>
            <ElFormItem v-if="!productId" prop="version_value" label="外观版本"><ElInput v-model="form.version_value" maxlength="100" placeholder="例如：V1、金色、亮银" /></ElFormItem>
            <ElFormItem prop="customer_name" label="客户名称">
              <ElSelect
                :model-value="customerSelection"
                placement="top-start"
                :fallback-placements="['top-start', 'top-end']"
                filterable
                allow-create
                default-first-option
                :loading="customerLoading"
                :disabled="customerLoading || Boolean(customerError)"
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

      <section id="product-bom" class="editor-card">
        <BomEditor
          :model-value="form.bom_items"
          :factory-code="form.factory_code"
          :readonly="versionReadOnly"
          :can-save="Boolean(productId && !versionReadOnly)"
          :dirty="bomDirty"
          :saving="activeAction === 'bom'"
          @update:model-value="updateBom"
          @save="performAction('bom', saveBom)"
        />
      </section>

      <section id="product-process" class="editor-card process-section">
        <ElAlert v-if="!productId" title="请先保存产品基础信息和 BOM，再配置工序流程" type="info" :closable="false" show-icon />
        <template v-else-if="editorReady">
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
            <template v-if="!versionReadOnly" #actions="{ disabled }">
              <ElButton
                plain
                :disabled="disabled || !flowDirty || store.saving"
                :loading="activeAction === 'flow-draft'"
                @click="performAction('flow-draft', saveFlowDraft)"
              >保存草稿</ElButton>
              <ElButton
                type="primary"
                :disabled="disabled || (!flowDirty && !form.process_flow_is_draft) || store.saving"
                :loading="activeAction === 'flow'"
                @click="performAction('flow', saveFlow)"
              >确认并保存流程</ElButton>
            </template>
          </ProcessFlowEditor>
        </template>
        <div v-else v-loading="true" class="flow-loading">正在加载流程图</div>
      </section>
    </template>
  </main>
</template>

<style scoped>
.editor-page { padding: 32px; }
.editor-heading :deep(.page-heading-actions) { width: 100%; }
.editor-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; width: 100%; padding: 16px; border: 1px solid var(--erp-border); border-radius: 8px; background: var(--erp-surface); }
.action-group { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }.action-group + .action-group { border-left: 1px solid var(--erp-border); padding-left: 12px; }.editor-actions :deep(.el-button) { margin: 0; }
.version-selector { display: flex; align-items: center; gap: 8px; margin-right: auto; color: var(--erp-text-muted); font-size: 12px; }.version-selector :deep(.el-select) { width: 120px; }
.editor-loading, .editor-card { min-width: 0; padding: 24px; margin-bottom: 24px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
.editor-loading p { margin: 16px 0 0; color: var(--erp-text-muted); }
.section-heading { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; margin-bottom: 24px; }.section-heading h2 { margin: 0 0 6px; font-size: 20px; font-weight: 600; }.section-heading span { color: var(--erp-text-muted); font-size: 12px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }.base-details { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 24px; margin: 0; padding: 20px; border-radius: 8px; background: var(--erp-surface-muted); }.base-details div { min-width: 0; }.base-details dt { color: var(--erp-text-muted); font-size: 12px; margin-bottom: 8px; }.base-details dd { margin: 0; font-size: 14px; overflow-wrap: anywhere; }
.section-alert, .flow-error { margin-bottom: 24px; }.flow-loading { display: grid; min-height: 260px; place-items: center; color: var(--erp-text-muted); }
.editor-navigation { position: sticky; top: 16px; z-index: 10; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0 0 24px; padding: 8px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); }
.editor-navigation a { min-height: 44px; display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 8px; color: var(--erp-text); font-size: 14px; font-weight: 500; }.editor-navigation a > span { color: var(--erp-primary); font-size: 12px; font-variant-numeric: tabular-nums; }.editor-navigation small { display: block; margin-top: 4px; color: var(--erp-text-muted); font-size: 12px; font-weight: 400; }
.editor-card { scroll-margin-top: 120px; }.basic-section { border-top: 3px solid var(--erp-primary); }
@media (hover: hover) and (pointer: fine) { .editor-navigation a:hover { background: var(--erp-primary-soft); } }
@media (max-width: 1000px) { .base-details { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .editor-page { padding: 24px 16px; }.editor-card { padding: 16px; }.editor-navigation { position: static; }.editor-navigation a { padding: 8px; gap: 8px; }.editor-navigation small { display: none; }.editor-card { scroll-margin-top: 16px; }.form-grid { grid-template-columns: 1fr; }.editor-actions { align-items: stretch; flex-direction: column; }.version-selector { justify-content: space-between; margin-right: 0; }.action-group { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }.action-group + .action-group { border-left: 0; border-top: 1px solid var(--erp-border); padding: 12px 0 0; } }
@media (max-width: 480px) { .editor-navigation a { font-size: 12px; }.editor-navigation a > span { display: none; }.base-details { grid-template-columns: 1fr; }.action-group { grid-template-columns: 1fr; } }
</style>
