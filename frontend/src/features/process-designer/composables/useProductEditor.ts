import { computed, onMounted, onScopeDispose, ref, useTemplateRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import type { ApiErrorDetail } from '@/api/types'
import { useAuthStore, PRODUCT_PERMISSIONS } from '@/features/identity'
import { useRequest } from '@/shared/query/useRequest'
import * as products from '../api/engineeringProducts'
import type { Appearance, BomItem, EngineeringProduct, ProcessFlow } from '../domain/types'
import { useProductDraft } from './useProductDraft'
import { useUnsavedChangesGuard } from './useUnsavedChangesGuard'

export type FlowEditorApi = {
  getGraphData: () => ProcessFlow
  reload: (flow: ProcessFlow) => void
  focusElement: (id?: string) => void
}
type Action = 'create' | 'base' | 'bom' | 'flow' | 'flow-draft' | 'appearance-create'

/** The page owns its document, navigation and operations; no feature-wide editor store. */
export function useProductEditor() {
  const route = useRoute(), router = useRouter(), auth = useAuthStore()
  const draft = useProductDraft()
  const { form } = draft
  const flowEditor = useTemplateRef<FlowEditorApi>('flowEditor')
  const activeAction = ref<Action | null>(null)
  const saving = computed(() => activeAction.value !== null)
  const productId = computed(() => {
    const id = Number(route.params.productId)
    return Number.isSafeInteger(id) && id > 0 ? id : null
  })
  const mode = computed(() => route.query.mode === 'view' ? 'view' : 'edit')
  const canEdit = computed(() => auth.hasPermission(productId.value ? PRODUCT_PERMISSIONS.edit : PRODUCT_PERMISSIONS.add))
  const documentRequest = useRequest<EngineeringProduct>('产品外观加载失败')
  const appearanceRequest = useRequest<Appearance[]>('产品外观列表加载失败')
  const appearances = computed(() => appearanceRequest.data.value ?? [])
  const requestedAppearance = ref<number>()
  const ready = ref(false)
  const flowSaveError = ref<ApiErrorDetail | null>(null)
  let epoch = 0, disposed = false
  const loading = computed(() => documentRequest.loading.value || appearanceRequest.loading.value)
  const contentReady = computed(() => ready.value && !loading.value && !documentRequest.error.value && !appearanceRequest.error.value)
  const baseReadOnly = computed(() => mode.value === 'view' || !canEdit.value || Boolean(productId.value && !draft.capabilities.baseEditable))
  const appearanceReadOnly = computed(() => mode.value === 'view' || !canEdit.value || saving.value || !contentReady.value
    || Boolean(productId.value && !draft.capabilities.appearanceEditable))
  useUnsavedChangesGuard(computed(() => mode.value === 'edit' && contentReady.value && draft.dirty.value))

  function clearFlowSaveError() { flowSaveError.value = null }
  function current(operation: number) { return !disposed && epoch === operation }
  function routeAppearance() {
    const appearance_id = Number(route.query.appearance_id)
    return Number.isSafeInteger(appearance_id) && appearance_id > 0 ? appearance_id : undefined
  }
  function syncRoute(appearance_id: number, nextMode = mode.value) {
    return router.replace({ query: { mode: nextMode, appearance_id: String(appearance_id) } })
  }

  async function loadAppearance(appearance_id?: number) {
    const id = productId.value
    if (!id || disposed) return false
    const operation = ++epoch
    activeAction.value = null
    ready.value = false
    requestedAppearance.value = appearance_id
    flowSaveError.value = null
    const product = await documentRequest.run(signal => products.queryProduct(id, appearance_id, signal))
    if (!product || !current(operation)) return false
    draft.load(product)
    requestedAppearance.value = product.appearance_id ?? undefined
    if (product.appearance_id) await syncRoute(product.appearance_id)
    if (current(operation)) ready.value = true
    return current(operation)
  }

  async function initialize() {
    const operation = ++epoch
    documentRequest.cancel()
    appearanceRequest.cancel()
    documentRequest.error.value = ''
    appearanceRequest.error.value = ''
    activeAction.value = null
    ready.value = false
    if (route.params.productId && !productId.value) {
      documentRequest.error.value = '产品编号无效'
      return
    }
    if (!productId.value) { draft.reset(); ready.value = true; return }
    const id = productId.value
    const available = await appearanceRequest.run(signal => products.queryProductAppearances(id, signal))
    if (available && current(operation)) await loadAppearance(routeAppearance())
  }

  async function confirmDiscard() {
    if (!draft.dirty.value) return true
    try {
      await ElMessageBox.confirm('当前产品资料有未保存内容，继续会丢失修改，是否继续？', '未保存修改', { type: 'warning' })
      return true
    } catch { return false }
  }

  async function persist(
    action: Action, request: () => Promise<EngineeringProduct>,
    commit: (product: EngineeringProduct) => void, message: string,
  ) {
    if (saving.value || !contentReady.value) return undefined
    const operation = epoch
    activeAction.value = action
    if (action.startsWith('flow')) flowSaveError.value = null
    try {
      const product = await request()
      if (!current(operation)) return undefined
      commit(product)
      ElMessage.success(message)
      return product
    } catch (cause) {
      if (!current(operation)) return undefined
      const detail = getApiErrorDetail(cause)
      if (action.startsWith('flow')) flowSaveError.value = detail ?? { code: 'flow_save_failed', message: '流程保存失败' }
      flowEditor.value?.focusElement(detail?.element_id)
      ElMessage.error(detail?.message || '保存失败，请重试')
      return undefined
    } finally {
      if (current(operation)) activeAction.value = null
    }
  }

  async function createProduct() {
    const error = draft.validateBase() || draft.validateBom() || (!form.appearance_name.trim() ? '请填写外观名称' : undefined)
    if (error) return ElMessage.warning(error)
    const operation = epoch
    const product = await persist('create', () => products.createProduct({
      ...draft.normalizedFields(), appearance_name: form.appearance_name.trim(), bom_items: draft.normalizedBom(),
    }), draft.load, '基础信息和 BOM 已保存，请继续配置流程')
    if (product && current(operation)) await router.replace(`/products/${product.id}`)
  }

  async function saveBase() {
    const id = productId.value, revision = form.revision
    if (!id || revision === null) return
    const error = draft.validateBase()
    if (error) return ElMessage.warning(error)
    await persist('base', () => products.updateProductInfo(id, revision, draft.normalizedFields()), draft.commitBase, '产品基础信息已保存')
  }

  async function saveBom() {
    const id = productId.value, appearance_id = form.appearance_id, revision = form.revision
    if (!id || appearance_id === null || revision === null) return
    const error = draft.validateBom()
    if (error) return ElMessage.warning(error)
    const flow = flowEditor.value?.getGraphData() ?? form.process_flow
    await persist('bom', () => products.replaceProductBom(id, revision, draft.normalizedBom()),
      product => { draft.commitBom(product, flow); flowEditor.value?.reload(form.process_flow) }, 'BOM 已保存')
  }

  async function saveFlow(isDraft: boolean) {
    const id = productId.value, appearance_id = form.appearance_id, revision = form.revision
    if (!id || appearance_id === null || revision === null || !flowEditor.value) return
    form.process_flow = flowEditor.value.getGraphData()
    const save = isDraft ? products.saveProductProcessFlowDraft : products.updateProductProcessFlow
    await persist(isDraft ? 'flow-draft' : 'flow', () => save(id, revision, appearance_id, form.process_flow),
      product => { draft.commitFlow(product); flowEditor.value?.reload(form.process_flow) }, isDraft ? '流程草稿已保存' : '工序流程已保存')
  }

  async function saveAppearanceName(rename = false) {
    const id = productId.value, appearanceId = form.appearance_id, revision = form.revision
    if (!id || !appearanceId || revision === null || saving.value) return
    if (draft.dirty.value) return ElMessage.warning('请先保存当前修改')
    const operation = epoch
    let name: string
    try {
      const result = await ElMessageBox.prompt(rename ? '填写外观名称' : '填写新外观名称，将复制当前外观正式流程', rename ? '重命名外观' : '新增外观', {
        inputValue: rename ? form.appearance_name : '', inputValidator: value => Boolean(value?.trim()) && value.trim().length <= 200 || '请填写1至200字外观名称',
      })
      name = result.value.trim()
    } catch { return }
    if (!current(operation)) return
    const product = await persist('appearance-create', () => rename
      ? products.renameProductAppearance(id, appearanceId, revision, name)
      : products.createProductAppearance(id, revision, name, appearanceId), draft.load, '外观已保存')
    if (product && current(operation)) {
      appearanceRequest.data.value = product.appearances
      requestedAppearance.value = product.appearance_id ?? undefined
      if (product.appearance_id) await syncRoute(product.appearance_id)
    }
  }

  async function switchAppearance(appearance_id?: number) {
    const operation = epoch
    if (await confirmDiscard() && current(operation)) await loadAppearance(appearance_id)
  }
  async function exitEdit() {
    const operation = epoch
    if (!await confirmDiscard() || !current(operation) || !form.appearance_id) return
    if (!draft.dirty.value || await loadAppearance(form.appearance_id)) await syncRoute(form.appearance_id, 'view')
  }

  onMounted(() => { void initialize() })
  watch(() => route.params.productId, () => { void initialize() }, { flush: 'sync' })
  watch(() => route.query.appearance_id, () => {
    const appearance_id = routeAppearance()
    if (contentReady.value && appearance_id !== form.appearance_id && productId.value) void loadAppearance(appearance_id)
  })
  watch(mode, nextMode => {
    if (nextMode === 'view' && contentReady.value && draft.dirty.value && form.appearance_id) {
      void loadAppearance(form.appearance_id)
    }
  })
  onScopeDispose(() => { disposed = true; epoch += 1 })
  return {
    ...draft, activeAction, saving, productId, mode, canEdit, contentReady,
    baseReadOnly, appearanceReadOnly, appearances, requestedAppearance, flowSaveError,
    initializing: appearanceRequest.loading, loadingProduct: documentRequest.loading,
    initializationError: appearanceRequest.error, productError: documentRequest.error,
    initialize, retry: () => loadAppearance(requestedAppearance.value),
    clearFlowSaveError, createProduct, saveBase, saveBom,
    saveFlow: () => saveFlow(false), saveFlowDraft: () => saveFlow(true), createAppearance: () => saveAppearanceName(), renameAppearance: () => saveAppearanceName(true), switchAppearance,
    enterEdit: () => form.appearance_id ? syncRoute(form.appearance_id, 'edit') : undefined, exitEdit,
    back: () => router.push('/products'), updateBom: (items: BomItem[]) => { form.bom_items = items },
  }
}
