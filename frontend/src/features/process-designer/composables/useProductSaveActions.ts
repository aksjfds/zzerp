import { ref, type Ref } from 'vue'
import type { Router } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import type { ApiErrorDetail } from '@/api/types'
import type { useEngineeringProductsStore } from '../stores/engineeringProducts'
import {
  synchronizeFlowPartMetadata,
  synchronizeAssemblyIdentity,
  type BomItem,
  type EngineeringProduct,
  type ProcessFlow,
  type ProductFields,
  type ProductForm,
} from '../domain/types'

export type FlowEditorApi = {
  focusElement: (elementId?: string) => void
  getGraphData: () => ProcessFlow
  reload: (flow: ProcessFlow) => void
}

type EditorFormApi = {
  applyProduct: (product: EngineeringProduct) => void
  bomSnapshot: Ref<string>
  flowSnapshot: Ref<string>
  form: ProductForm
  markSaved: (sections: Array<'base' | 'bom' | 'flow'>) => void
  normalizedBom: () => BomItem[]
  normalizedFields: () => ProductFields
  validateBom: () => string | null
}

type Options = EditorFormApi & {
  editorReady: Ref<boolean>
  flowEditor: Ref<FlowEditorApi | undefined>
  productId: Ref<number | null>
  router: Router
  store: ReturnType<typeof useEngineeringProductsStore>
  validateBase: () => Promise<boolean>
}

export function useProductSaveActions(options: Options) {
  const {
    applyProduct, bomSnapshot, editorReady, flowEditor, flowSnapshot, form,
    markSaved, normalizedBom, normalizedFields, productId, router, store,
    validateBase, validateBom,
  } = options
  const flowSaveError = ref<ApiErrorDetail | null>(null)

  async function createProduct() {
    if (!await validateBase()) return
    const bomError = validateBom()
    if (bomError) return ElMessage.error(bomError)
    try {
      Object.assign(form, normalizedFields(), { bom_items: normalizedBom() })
      const product = await store.createProduct(form)
      applyProduct(product)
      editorReady.value = true
      markSaved(['base', 'bom', 'flow'])
      ElMessage.success('基础信息和 BOM 已保存，请继续配置流程')
      await router.replace(`/products/${product.id}`)
    } catch (error) {
      showSaveError(error, '产品创建失败')
    }
  }

  async function saveBom() {
    if (!productId.value || form.revision === null || form.version === null) return
    const bomError = validateBom()
    if (bomError) return ElMessage.error(bomError)
    try {
      const localFlow = flowEditor.value?.getGraphData() ?? form.process_flow
      const product = await store.saveProductBom(
        productId.value,
        form.revision,
        form.version,
        normalizedBom(),
      )
      form.version = product.version
      form.revision = product.revision
      form.bom_items = product.bom_items.map((item) => ({ ...item }))
      form.process_flow = synchronizeFlowPartMetadata(
        localFlow,
        form.bom_items,
        form.factory_code,
      )
      flowEditor.value?.reload(form.process_flow)
      bomSnapshot.value = JSON.stringify(form.bom_items)
      flowSnapshot.value = JSON.stringify(product.process_flow)
      ElMessage.success('BOM 已保存')
    } catch (error) {
      showSaveError(error, 'BOM 保存失败')
    }
  }

  async function saveProductInfo() {
    if (!productId.value || form.revision === null || !await validateBase()) return
    try {
      const fields = normalizedFields()
      const product = await store.saveProductInfo(
        productId.value,
        form.revision,
        fields,
      )
      Object.assign(form, fields, {
        customer_id: product.customer_id,
        customer_name: product.customer_name,
        product_name: product.product_name,
        factory_code: product.factory_code,
        customer_code: product.customer_code,
        revision: product.revision,
      })
      form.process_flow = product.process_flow
      flowEditor.value?.reload(product.process_flow)
      flowSnapshot.value = JSON.stringify(product.process_flow)
      markSaved(['base', 'flow'])
      ElMessage.success('产品基础信息已保存')
    } catch (error) {
      showSaveError(error, '产品基础信息保存失败')
    }
  }

  async function saveFlow() {
    if (!productId.value || form.revision === null || form.version === null || !flowEditor.value) return
    flowSaveError.value = null
    form.process_flow = synchronizeAssemblyIdentity(
      flowEditor.value.getGraphData(),
      form.factory_code,
    )
    try {
      const product = await store.saveProcessFlow(
        productId.value,
        form.revision,
        form.version,
        form.process_flow,
      )
      form.version = product.version
      form.revision = product.revision
      form.process_flow = product.process_flow
      flowEditor.value.reload(product.process_flow)
      markSaved(['flow'])
      ElMessage.success('工序流程已保存')
    } catch (error) {
      showSaveError(error, '流程保存失败', true)
    }
  }

  function showSaveError(error: unknown, fallback: string, isFlowError = false) {
    const detail = getApiErrorDetail(error)
    if (isFlowError) {
      flowSaveError.value = detail || {
        code: 'flow_save_failed',
        message: fallback,
      }
    }
    flowEditor.value?.focusElement(detail?.element_id)
    ElMessage.error(
      detail?.code === 'product_version_conflict'
        ? '资料已被其他用户更新，请返回列表后重新打开'
        : detail?.message || fallback,
    )
  }

  function clearFlowSaveError() {
    flowSaveError.value = null
  }

  return {
    clearFlowSaveError,
    createProduct,
    flowSaveError,
    saveBom,
    saveFlow,
    saveProductInfo,
  }
}
