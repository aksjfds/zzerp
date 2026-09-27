import { onScopeDispose, ref, watch, type ComputedRef, type Ref } from 'vue'
import type { Router } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import type { useEngineeringProductsStore } from '../stores/engineeringProducts'
import { queryProductVersions } from '../api/engineeringProducts'
import type { EngineeringProduct } from '../domain/types'

type Options = {
  applyProduct: (product: EngineeringProduct) => void
  editorReady: Ref<boolean>
  markSaved: (sections: Array<'base' | 'bom' | 'flow'>) => void
  mode: ComputedRef<string>
  productId: ComputedRef<number | null>
  router: Router
  store: ReturnType<typeof useEngineeringProductsStore>
  versionDirty: ComputedRef<boolean>
}

export function useProductVersionLoader(options: Options) {
  const {
    applyProduct,
    editorReady,
    markSaved,
    mode,
    productId,
    router,
    store,
    versionDirty,
  } = options
  const baseInfoEditable = ref(false)
  const currentVersion = ref<number>()
  const loadingProduct = ref(false)
  const versionEditable = ref(false)
  const versions = ref<number[]>([])
  const productError = ref('')
  const requestedVersion = ref<number>()
  let productRequest = 0
  let versionsRequest = 0

  watch(productId, () => {
    productRequest++
    versionsRequest++
    loadingProduct.value = false
    productError.value = ''
    requestedVersion.value = undefined
    currentVersion.value = undefined
    versions.value = []
    baseInfoEditable.value = false
    versionEditable.value = false
    editorReady.value = false
  }, { flush: 'sync' })

  async function loadProductVersion(version?: number) {
    const id = productId.value
    if (!id) return false
    const request = ++productRequest
    requestedVersion.value = version
    productError.value = ''
    loadingProduct.value = true
    editorReady.value = false
    try {
      const product = await store.loadProduct(id, version)
      if (request !== productRequest || id !== productId.value) return false
      applyProduct(product)
      requestedVersion.value = product.version
      currentVersion.value = product.current_version
      baseInfoEditable.value = product.base_info_editable
      versionEditable.value = product.version_editable
      editorReady.value = true
      markSaved(['base', 'bom', 'flow'])
      await router.replace({
        query: {
          mode: mode.value,
          ...(version ? { version: String(version) } : {}),
        },
      })
      return request === productRequest
    } catch (error) {
      if (request === productRequest && id === productId.value) {
        productError.value = getApiErrorDetail(error)?.message || '产品版本加载失败'
        editorReady.value = false
      }
      return false
    } finally {
      if (request === productRequest) loadingProduct.value = false
    }
  }

  async function reloadVersions() {
    const id = productId.value
    if (!id) return
    const request = ++versionsRequest
    const result = await queryProductVersions(id)
    if (request === versionsRequest && id === productId.value) versions.value = result
  }

  async function switchVersion(version?: number) {
    if (!productId.value) return
    if (versionDirty.value) {
      try {
        await ElMessageBox.confirm(
          '当前产品基础信息、BOM 或流程有未保存内容，切换版本会丢失修改，是否继续？',
          '未保存修改',
          {
            type: 'warning',
            confirmButtonText: '继续切换',
            cancelButtonText: '继续编辑',
          },
        )
      } catch {
        return
      }
    }
    await loadProductVersion(version)
  }

  function retryProductVersion() {
    return loadProductVersion(requestedVersion.value)
  }

  onScopeDispose(() => {
    productRequest++
    versionsRequest++
  })

  return {
    baseInfoEditable,
    currentVersion,
    loadingProduct,
    productError,
    requestedVersion,
    retryProductVersion,
    loadProductVersion,
    reloadVersions,
    switchVersion,
    versionEditable,
    versions,
  }
}
