import { ref, type ComputedRef, type Ref } from 'vue'
import type { Router } from 'vue-router'
import { ElMessageBox } from 'element-plus'
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
  const baseInfoEditable = ref(true)
  const currentVersion = ref<number>()
  const loadingProduct = ref(false)
  const versionEditable = ref(true)
  const versions = ref<number[]>([])

  async function loadProductVersion(version?: number) {
    if (!productId.value) return
    loadingProduct.value = true
    try {
      const product = await store.loadProduct(productId.value, version)
      applyProduct(product)
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
    } finally {
      loadingProduct.value = false
    }
  }

  async function reloadVersions() {
    if (!productId.value) return
    versions.value = await queryProductVersions(productId.value)
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

  return {
    baseInfoEditable,
    currentVersion,
    loadingProduct,
    loadProductVersion,
    reloadVersions,
    switchVersion,
    versionEditable,
    versions,
  }
}
