<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import BomEditor from '../components/BomEditor.vue'
import ProcessFlowEditor from '../components/ProcessFlowEditor.vue'
import { type BomItem, type ProcessFlow, type ProductFields } from '../domain/types'
import { useEngineeringProductsStore } from '@/stores/engineeringProducts'
import { useAuthStore } from '@/stores/auth'
import { PRODUCT_PERMISSIONS } from '@/permission/constants'
import { useProductEditorForm } from '../composables/useProductEditorForm'
import { useProductSaveActions } from '../composables/useProductSaveActions'
import { useUnsavedChangesGuard } from '../composables/useUnsavedChangesGuard'
import { queryProductVersions } from '../api/engineeringProducts'

type FlowEditorApi = {
  focusElement: (elementId?: string) => void
  getGraphData: () => ProcessFlow
  reload: (flow: ProcessFlow) => void
}

const route = useRoute()
const router = useRouter()
const store = useEngineeringProductsStore()
const authStore = useAuthStore()
const baseFormRef = ref<FormInstance>()
const flowEditor = ref<FlowEditorApi>()
const editorReady = ref(false)
const versions = ref<number[]>([])
const currentVersion = ref<number>()
const {
  applyProduct,
  baseDirty,
  bomDirty,
  bomSnapshot,
  flowDirty,
  flowSnapshot,
  form,
  hasUnsavedChanges,
  markSaved,
  normalizedBom,
  normalizedFields,
  validateBom,
} = useProductEditorForm()

const productId = computed(() => {
  const value = Number(route.params.productId)
  return Number.isInteger(value) && value > 0 ? value : null
})
const readOnly = computed(() => Boolean(
  !authStore.hasPermission(PRODUCT_PERMISSIONS.edit)
  || (form.version && currentVersion.value && form.version !== currentVersion.value),
))

const baseRules: FormRules<ProductFields> = {
  customer_name: [{ required: true, whitespace: true, message: '请输入客户名称', trigger: 'blur' }],
  product_name: [{ required: true, whitespace: true, message: '请输入产品名称', trigger: 'blur' }],
  factory_code: [{ required: true, whitespace: true, message: '请输入本厂型号', trigger: 'blur' }],
  customer_code: [{ required: true, whitespace: true, message: '请输入客户型号', trigger: 'blur' }],
}

async function validateBase() {
  try {
    await baseFormRef.value?.validate()
    return true
  } catch {
    return false
  }
}

const { createProduct, saveBase, saveBom, saveFlow } = useProductSaveActions({
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

useUnsavedChangesGuard(hasUnsavedChanges)

async function loadVersion(version?: number) {
  if (!productId.value) return
  const product = await store.loadProduct(productId.value, version)
  applyProduct(product)
  currentVersion.value = product.current_version
  editorReady.value = true
  markSaved(['base', 'bom', 'flow'])
  await router.replace({ query: version ? { version: String(version) } : {} })
}

onMounted(async () => {
  if (!productId.value) {
    markSaved(['base', 'bom', 'flow'])
    return
  }
  try {
    versions.value = await queryProductVersions(productId.value)
    const requestedVersion = Number(route.query.version)
    await loadVersion(Number.isInteger(requestedVersion) && requestedVersion > 0
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
        <div class="page-kicker">工程部 / {{ productId ? '编辑产品' : '录入产品' }}</div>
        <h1>{{ productId ? form.product_name || '编辑产品' : '录入新产品' }}</h1>
      </div>
      <div>
        <ElSelect
          v-if="productId"
          :model-value="form.version"
          style="width: 110px; margin-right: 10px"
          @change="loadVersion"
        >
          <ElOption v-for="version in versions" :key="version" :label="`V${version}`" :value="version" />
        </ElSelect>
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
        <div><h2>产品基础信息</h2><span>所有字段均为必填</span></div>
        <ElButton v-if="productId && !readOnly" type="primary" plain :disabled="!baseDirty" :loading="store.saving" @click="saveBase">保存基础信息</ElButton>
      </div>
      <ElForm ref="baseFormRef" :model="form" :rules="baseRules" :disabled="readOnly" label-position="top">
        <div class="form-grid">
          <ElFormItem prop="customer_name" label="客户名称"><ElInput v-model="form.customer_name" /></ElFormItem>
          <ElFormItem prop="product_name" label="产品名称"><ElInput v-model="form.product_name" /></ElFormItem>
          <ElFormItem prop="factory_code" label="产品的本厂型号"><ElInput v-model="form.factory_code" /></ElFormItem>
          <ElFormItem prop="customer_code" label="产品的客户型号"><ElInput v-model="form.customer_code" /></ElFormItem>
        </div>
      </ElForm>
    </section>

    <section class="editor-card">
      <div class="section-action">
        <ElButton v-if="productId && !readOnly" type="primary" plain :disabled="!bomDirty" :loading="store.saving" @click="saveBom">保存 BOM</ElButton>
      </div>
      <div :class="{ 'read-only-content': readOnly }"><BomEditor :model-value="form.bom_items" @update:model-value="updateBom" /></div>
    </section>

    <section class="editor-card">
      <ElAlert v-if="!productId" title="请先保存产品基础信息和 BOM，再配置工序流程" type="info" :closable="false" show-icon />
      <template v-else-if="editorReady">
        <ElAlert v-if="readOnly" title="历史版本为只读" type="info" :closable="false" />
        <div v-if="!readOnly" class="section-action"><ElButton type="primary" plain :disabled="!flowDirty" :loading="store.saving" @click="saveFlow">保存工序流程</ElButton></div>
        <div :class="{ 'read-only-content': readOnly }"><ProcessFlowEditor ref="flowEditor" v-model="form.process_flow" :bom-items="form.bom_items" /></div>
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
.page-kicker { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.editor-card { margin-bottom: 18px; padding: 20px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-heading > div { display: flex; align-items: baseline; gap: 12px; }
.section-heading h2 { margin: 0; font-size: 18px; }
.section-heading span { color: var(--el-text-color-secondary); font-size: 12px; }
.section-action { display: flex; justify-content: flex-end; margin-bottom: 12px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 20px; }
.basic-section :deep(.el-form-item) { margin-bottom: 12px; }
.flow-loading { display: grid; min-height: 260px; place-items: center; color: var(--el-text-color-secondary); }
.read-only-content { pointer-events: none; opacity: .82; }
@media (max-width: 680px) { .editor-page { padding: 12px; } .editor-header { align-items: flex-start; flex-direction: column; } .form-grid { grid-template-columns: 1fr; } }
</style>
